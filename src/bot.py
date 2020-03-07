from time import time, sleep
import random
import src.lib.irc as irc_
import src.lib.functions_general as general
import src.lib.functions_commands as commands
import src.lib.sql_table as db
from pony.orm import db_session
from datetime import datetime


class Main:
	def __init__(self, config):
		self.config = config
		self.irc = irc_.irc(config)
		self.socket = self.irc.get_irc_socket_object
		self.balance = 0

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

	def bet_logic(self, target_channel, total_d, bet_dict):
		# Set the bet amount.
		bet = random.randint(500, 1500)
		# Choose a side
		ratio = int(total_d.get('blue_amt', 0)) / (int(total_d.get('red_amt', 0)) + int(total_d.get('blue_amt', 1)))
		if 0.4 < ratio < 0.6:
			side = random.choice(['blue', 'red'])
		else:
			side = 'blue' if int(total_d.get('blue_amt', 0)) > int(total_d.get('red_amt', 0)) else 'red'
			bet = random.randint(1000, 3000)

		# Send the message and record the bet.
		self.irc.send_message(target_channel, f'!{side} {bet}')
		print(f'Bet complete: !{side} {bet}\n')
		you_bet = True
		bet_dict['bet_team'] = side
		return you_bet, bet_dict

	@db_session
	def update_bet(self, side, bet_amount, balance, ratio, teams):
		# Try to update previous record if it exists.
		database = db.db
		update_win = database.select('select * from BalanceRecord order by ID desc limit 1')
		update_key = 0
		if update_win:
			update_key = update_win[0][0]
			update_db = db.BalanceRecord[update_key]
			try:
				self.balance = int(balance) + int(bet_amount)
			except Exception as e:
				raise Exception(f'{e} and {balance} {bet_amount}')
			update_db.win_status = False if update_win[0][9] >= self.balance else True
		# Update current entry.
		update_key += 1
		update_bet = db.BalanceRecord(time=datetime.utcnow(), starting_balance=self.balance, bet_amt=bet_amount,
									  bet_ratio=ratio, bet_side=side, favored_side=side if ratio >= 0.5 else teams[f'{side}'],
									  new_balance=int(balance))
		database.flush()
		database.commit()
		self.balance = int(balance)
		return database.select('select * from BalanceRecord order by ID desc limit 1')

	@db_session
	def check_salty_message(self, message, totals, time_dict, bet_dict):
		teams = {'blue': 'red', 'red': 'blue'}

		if f'@{self.config["username"]} - Bet complete' in message:
			bet_message = message.split(' - Bet complete for ')[1].split(', ')
			bet_dict['bet_team'] = bet_message[0].lower()
			bet_ints = bet_message[1].split('.')
			bet_dict['bet_amount'] = int(bet_ints[0])
			bet_dict['new_balance'] = int(bet_ints[1].strip('Your new balance is '))
			bet_dict['bet_complete'] = True
			print("Bet Acknowledged")

		if "Bet complete" in message:
			# This is the first bet of the game.
			if totals['blue_amt'] == 0 and totals['red_amt'] == 0:
				time_dict['first_bet'] = time()
				time_dict['bet_timer'] = 0
				bet_dict['betting_started'] = True
			split = message.split(' - Bet complete for ')[1].split(', ')
			team = split[0].lower()
			amt = int(split[1].split('.')[0])

			# Increment totals each time a user bets.
			if team == 'blue':
				totals['blue_amt'] += amt
				totals['blue_bets'] += 1
			else:
				totals['red_amt'] += amt
				totals['red_bets'] += 1

			print(f"Time since first bet: {time_dict['bet_timer']} s")
			print(f'Blue: \t{"{:,}".format(totals["blue_amt"])} shrooms, {totals["blue_bets"]} bets')
			print(f'Red: \t{"{:,}".format(totals["red_amt"])} shrooms, {totals["red_bets"]} bets\n')

		# Message contains 'Betting has ended' or over 3 minutes has passed, and we bet.
		if 'Betting has ended' in message or time_dict['bet_timer'] >= 210:
			if totals['blue_amt'] != 0 and totals['red_amt'] != 0:
				if 'name' not in lower:
					lower['name'] = 'UNKNOWN'
				bet_team = bet_dict.get('bet_team')
				bet_amount = bet_dict.get('bet_amount')
				new_balance = bet_dict.get('new_balance', 0)

				# Logic for SQLite db
				if bet_dict.get('bet_complete'):
					other = teams[f'{bet_team}']
					ratio_calc = int(totals[f'{bet_team}_amt']) / \
								 (int(totals[f'{bet_team}_amt']) + int(totals[f'{other}_amt']))
					entry = self.update_bet(bet_team, bet_amount, new_balance, ratio_calc, teams)
					print(f"inserted {entry}")

				# Resetting values at the end of betting.
				totals = {'blue_amt': 0, 'blue_bets': 0, 'red_amt': 0, 'red_bets': 0}
				time_dict['first_bet'] = 0
				time_dict['bet_timer'] = 0
				bet_dict['bet_complete'] = False
				bet_dict['betting_started'] = False

				print('Betting has ended\n')

		if f"{self.config['username']} - You have " in message:
			balance = message.split("- You have ")[1].split("mushrooms.")[0].strip()
			old_balance = self.balance or db.db.BalanceRecord.select_by_sql('select * from BalanceRecord '
																			'order by ID desc limit 1')[0].new_balance
			if balance != old_balance:
				update = db.BalanceRecord(time=datetime.utcnow(), starting_balance=self.balance,
										  bet_amt=(int(balance) - old_balance),
										  farm_event=True, new_balance=int(balance))
			db.db.flush()
			db.db.commit()
			self.balance = balance

		return totals, time_dict, bet_dict

	def run(self):
		irc = self.irc
		sock = self.socket
		config = self.config

		global higher, lower

		# Initialize reusable properties.
		timers = {'!farm': time(), 'first_bet': time(), 'bet_timer': 0}
		totals = {'blue_amt': 0, 'blue_bets': 0, 'red_amt': 0, 'red_bets': 0}
		higher = lower = {}
		bet_info = {'bet_complete': False, 'betting_started': False}

		while True:
			time_since_collect = int(time() - timers['!farm'])
			timers['bet_timer'] = int(time() - timers['first_bet'])

			# Check for PING; reply with PONG.
			data = sock.recv(2048).rstrip()
			irc.check_for_ping(data)
			message_dict, channel, message, username = self.check_for_message(irc, data)

			# Check if 121 minutes has passed yet.
			if time_since_collect > 7300:
				irc.send_message(channel, '!farm')
				irc.send_message(channel, "!balance")
				timers['!farm'] = time()

			# Wait until 170 seconds has passed to bet.
			if timers['bet_timer'] >= 170 and bet_info['betting_started'] and not bet_info['bet_complete']:
				bet_info['bet_complete'], bet_info = self.bet_logic(channel, totals, bet_info)

			# Check if the script is still connected to IRC.
			if len(data) == 0:
				general.pp('Connection was lost, reconnecting...')
				sock = self.irc.get_irc_socket_object

			# Check if most recent data is a message from Twitch chat.
			if username:
				if username == 'xxsaltbotxx':
					# Message contains 'bet complete for'.
					totals, timers, bet_info = self.check_salty_message(message, totals, timers, bet_info)

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
