from time import time, sleep
import random
import src.lib.irc as irc_
import src.lib.functions_general as general
import src.lib.functions_commands as commands
import src.lib.sql_table as db
from pony.orm import db_session
from datetime import datetime


class Main:
	"""
	Primary execution class wrapper. This class manages the connection to IRC, providing both messages and message
	reading. This claos also contains the logic for placing bets and the SQLite record writing to dynamically record the
	bets and prior bet results.

	Methods:
		check_for_message: gets the message logs from IRC, returning the channel, message, and user objects separately.
		bet_logic: controls the logic for choosing a side to bet, and how much to bet.
		update_bet: updates SQLite db with bet record and prior record's win status
		check_salty_message: uses saltybot messages to track the status of live betting, including self-provided bets
		run: provides logic for maintaining ongoing bets.
	"""
	def __init__(self, config):
		self.config = config
		self.irc = irc_.irc(config)
		self.socket = self.irc.get_irc_socket_object
		self.balance = 0
		self.bet_dict = {'bet_team': None,
						 'bet_amt': 0,
						 'new_balance': 0,
						 'bet_complete': False,
						 'bet_submitted': False,
						 'betting_started': False}
		self.totals = {'blue_amt': 0,
					   'red_amt': 0,
					   'blue_bets': 0,
					   'red_bets': 0}

	@staticmethod
	def check_for_message(irc, stuff):
		mes_dict = {}
		chan, mes, user = None, None, None
		if irc.check_for_message(stuff):
			mes_dict = irc.get_message(stuff)
			chan = mes_dict['channel']
			mes = mes_dict['message']
			user = mes_dict['username']
		return mes_dict, chan, mes, user

	def bet_logic(self, target_channel):
		# Getting stats about the match at the time of betting.
		ratio = int(self.totals.get('blue_amt', 0)) / \
				(int(self.totals.get('red_amt', 0)) + int(self.totals.get('blue_amt', 1)))
		print(f'{ratio}')
		# Using stats to guide bet logic.
		if ratio <= 0.125 or ratio >= 0.875:
			side = 'red' if int(self.totals.get('blue_amt', 0)) > int(self.totals.get('red_amt', 0)) else 'blue'
			bet = random.randint(200, 500)
		elif 0.35 < ratio < 0.65:
			side = random.choice(['blue', 'red'])
			bet = random.randint(500, 1500)
		# Currently, in cases where ratio is between .15-.4, and .6-.85
		else:
			blue_betters_ratio = int(self.totals.get('blue_amt', 0)) / int(self.totals.get('blue_bets', 1))
			red_betters_ratio = int(self.totals.get('red_amt', 0)) / int(self.totals.get('red_bets', 1))
			betters_to_bet = blue_betters_ratio / red_betters_ratio
			if 0.33 < betters_to_bet < 3:
				side = 'blue' if int(self.totals.get('blue_amt', 0)) < int(self.totals.get('red_amt', 0)) else 'red'
				bet = random.randint(1000, 2000)
				print(f"ratio of betters is fine: {betters_to_bet}")
			else:
				side = 'blue' if float(betters_to_bet) < 0.33 else 'red'
				bet = random.randint(500, 1500)
				print(f"ratio of betters is crazy: {betters_to_bet}")

		# Send the message and record the bet.
		self.irc.send_message(target_channel, f'!{side} {bet}')
		print(f'Bet complete: !{side} {bet}\n')
		self.bet_dict['bet_team'] = side
		self.bet_dict['bet_amount'] = bet

	@db_session
	def update_bet(self, side, bet_amount, balance, ratio, teams):
		# Try to update previous record if it exists.
		database = db.db
		update_win = database.select("select * from BalanceRecord order by ID desc limit 2")
		if update_win:
			update_key = update_win[0][0] if bool(update_win[0][2]) is False else update_win[1][0]
			update_db = db.BalanceRecord[update_key]
			try:
				self.balance = int(balance) + int(bet_amount)
			except Exception as e:
				raise Exception(f'{e} and {balance} {bet_amount}')
			update_db.win_status = False if update_win[0][9] >= self.balance else True
		else:
			print("Couldn't find any existing records. Creating first record.")
			update_key = 0
		# Update current entry.
		update_key += 1
		update_bet = db.BalanceRecord(time=datetime.utcnow(), starting_balance=self.balance, bet_amt=bet_amount,
									  bet_ratio=ratio, bet_side=side, favored_side=side if ratio >= 0.5 else teams[f'{side}'],
									  new_balance=int(balance))
		database.flush()
		database.commit()
		self.balance = int(balance)
		return database.select("select * from BalanceRecord order by ID desc limit 1")

	@db_session
	def check_salty_message(self, message, time_dict):
		teams = {'blue': 'red', 'red': 'blue'}

		if f'@{self.config["username"]} - Bet complete' in message:
			bet_message = message.split(' - Bet complete for ')[1].split(', ')
			self.bet_dict['bet_team'] = bet_message[0].lower()
			bet_ints = bet_message[1].split('.')
			self.bet_dict['bet_amount'] = int(bet_ints[0])
			self.bet_dict['new_balance'] = int(bet_ints[1].strip('Your new balance is '))
			self.bet_dict['bet_complete'] = True  # This marker tracks from Salty Teemo whether a manual bet took place.
			self.bet_dict['bet_submitted'] = True  # This marker tracks the bot bet to ensure only one bet happens.
			print("Bet Acknowledged")

		if "Bet complete" in message:
			# This is the first bet of the game.
			if self.totals['blue_amt'] == 0 and self.totals['red_amt'] == 0:
				time_dict['first_bet'] = time()
				time_dict['bet_timer'] = 0
				self.bet_dict['betting_started'] = True
			split = message.split(' - Bet complete for ')[1].split(', ')
			team = split[0].lower()
			amt = int(split[1].split('.')[0])

			# Increment totals each time a user bets.
			if team == 'blue':
				self.totals['blue_amt'] += amt
				self.totals['blue_bets'] += 1
			else:
				self.totals['red_amt'] += amt
				self.totals['red_bets'] += 1

			print(f"Time since first bet: {time_dict['bet_timer']} s")
			print(f'\033[34m Blue: \t{"{:,}".format(self.totals["blue_amt"])} shrooms, {self.totals["blue_bets"]} bets\033[00m',
				  f'\033[31m Red: \t{"{:,}".format(self.totals["red_amt"])} shrooms, {self.totals["red_bets"]} bets\033[00m',
				  sep=' || ', flush=True)

		# Message contains 'Betting has ended' or over 3 minutes has passed, and we bet.
		if 'Betting has ended' in message or time_dict['bet_timer'] >= 210:
			if self.totals['blue_amt'] != 0 and self.totals['red_amt'] != 0:
				if 'name' not in lower:
					lower['name'] = 'UNKNOWN'
				bet_team = self.bet_dict.get('bet_team')
				bet_amount = self.bet_dict.get('bet_amount')
				new_balance = self.bet_dict.get('new_balance', 0)

				other = teams.get(f'{bet_team}')
				ratio_calc = int(self.totals.get(f'{bet_team}_amt', 0)) / \
							 (int(self.totals.get(f'{other}_amt', 0)) + int(self.totals.get(f'{bet_team}_amt', 1)))

				# Logic for SQLite db
				if self.bet_dict.get('bet_complete'):
					red = "\033[31m"
					blue = "\033[34m"
					entry = self.update_bet(bet_team, bet_amount, new_balance, ratio_calc, teams)[0]
					print(f"""{red if bet_team=='red' else blue}
	Bet details:
        starting: {entry[3]}
        ending: {entry[9]}
        bet amount: {entry[5]}
        bet side: {entry[6]}
        favored side: {entry[7]}
        ratio: {entry[8]}\033[00m""")
				# Resetting values at the end of betting.
				self.totals = {'blue_amt': 0, 'blue_bets': 0, 'red_amt': 0, 'red_bets': 0}
				self.bet_dict = {'bet_team': None,
								 'bet_amt': 0,
								 'new_balance': 0,
								 'bet_complete': False,
								 'bet_submitted': False,
								 'betting_started': False}
				time_dict['first_bet'] = 0
				time_dict['bet_timer'] = 0

				print('Betting has ended\n')

		if f"{self.config['username']} - You find " in message:
			new_shrooms = int(message.split("- You find ")[1].split("mushrooms.")[0].strip())
			old_balance = self.balance or int(db.db.BalanceRecord.select_by_sql('select * from BalanceRecord '
																				'order by ID desc limit 1')[0].new_balance)
			update = db.BalanceRecord(time=datetime.utcnow(), starting_balance=old_balance,
										  bet_amt=new_shrooms,
										  farm_event=True, new_balance=(old_balance+new_shrooms))
			db.db.flush()
			db.db.commit()
			self.balance = int(old_balance) + new_shrooms

		return time_dict

	def run(self):
		irc = self.irc
		sock = self.socket
		config = self.config

		global higher, lower

		# Initialize reusable properties.
		timers = {'!farm': time(), 'first_bet': time(), 'bet_timer': 0}
		higher = lower = {}

		while True:
			time_since_collect = int(time() - timers['!farm'])
			timers['bet_timer'] = int(time() - timers['first_bet'])

			# Check for PING; reply with PONG.
			data = sock.recv(2048).rstrip()
			irc.check_for_ping(data)
			message_dict, channel, message, username = self.check_for_message(irc, data)

			# Check if 180 minutes has passed since start.
			if time_since_collect > 10800:
				irc.send_message(channel, '!farm')
				timers['!farm'] = time()

			# Wait until 170 seconds has passed to bet.
			if timers['bet_timer'] >= 160 \
					and self.bet_dict.get('betting_started')\
					and not self.bet_dict.get('bet_submitted'):
				self.bet_logic(channel)
				self.bet_dict['bet_submitted'] = True

			# Check if the script is still connected to IRC.
			if len(data) == 0:
				general.pp('Connection was lost, reconnecting...')
				sock = self.irc.get_irc_socket_object

			# Check if most recent data is a message from Twitch chat.
			if username:
				if username == 'xxsaltbotxx':
					# Message contains 'bet complete for'.
					timers = self.check_salty_message(message, timers)

				if username == config['username']:
					if config['log_messages']:
						general.ppi(channel, message, username)

					# Check if the message is a command (i.e. starts with "!{command}").
					if commands.is_valid_command(message) or commands.is_valid_command(message.split(' ')[0]):
						command = message

						# Command is a function (i.e. command should execute a script in the /src/lib/commands/ directory).
						if commands.check_returns_function(command.split(' ')[0]):
							if commands.check_has_correct_args(command, command.split(' ')[0]):
								args = command.split(' ')
								del args[0]
								command = command.split(' ')[0]

								if commands.is_on_cooldown(command, channel):
									general.pbot(f'Command is on cooldown. ({command}) ({username})' 
												 f'({commands.get_cooldown_remaining(command, channel)}s remaining)',
												 channel)
								else:
									# Command (function) is not on cooldown, so send a message to Twitch chat.
									general.pbot(f'({command}) ({username})', channel)
									result = commands.pass_to_function(command, args)

									if result:
										# Function returned a valid result.
										general.pbot(result, channel)
										irc.send_message(channel, result)
										commands.update_last_used(command, channel)

						# Command is not a function and has no arguments (i.e. a simple command with a simple response,
						# such as "!test").
						else:
							if commands.is_on_cooldown(command, channel):
								general.pbot(f'Command is on cooldown. ({command}) ({username}) ' 
											 f'({commands.get_cooldown_remaining(command, channel)}s remaining)',
											 channel)
							elif commands.check_has_return(command):
								# Command is not on cooldown, so send a message to Twitch chat.
								general.pbot(f'({command}) ({username})', channel)
								res = commands.get_return(command)
								general.pbot(res, channel)
								irc.send_message(channel, res)
								commands.update_last_used(command, channel)
