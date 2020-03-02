from time import time, sleep
import random
import src.lib.irc as irc_
import src.lib.functions_general as general
import src.lib.functions_commands as commands
import src.lib.sql_table as db
from pony.orm import db_session


class Main:
	def __init__(self, config):
		self.config = config
		self.irc = irc_.irc(config)
		self.socket = self.irc.get_irc_socket_object
		self.balance = 0

	def check_for_message(self, irc, stuff):
		mes_dict = {}
		chan, mes, user = None, None, None
		if irc.check_for_message(stuff):
			mes_dict = irc.get_message(stuff)
			chan = mes_dict['channel']
			mes = mes_dict['message']
			user = mes_dict['username']
		return mes_dict, chan, mes, user

	def bet_logic(self, target_channel, side):
		# Set the bet amount.
		bet = random.randint(500, 1500)
		# Send the message and record the bet.
		self.irc.send_message(target_channel, f'!{side} {bet}')
		print(f'Bet complete: !{side} {bet}\n')
		you_bet = True
		bet_started = False
		return you_bet, bet_started

	@db_session
	def check_balance(self, target_channel):
		self.irc.send_message(target_channel, "!balance")
		message_dict, chan, mes, user = self.check_for_message(self.irc)
		if f"{self.config['username']} - You have" in mes and user == "xxsaltbotxx":
			balance = mes.split("- You have ")[1].split("mushrooms.")[0].strip()
			update_farm = db.BalanceRecord()
			update_farm.farm_event = True
			update_farm.starting_balance = int(balance)
			return int(balance)

	@db_session
	def update_bet(self, side, bet_amount, balance, ratio):
		# Try to update previous record if it exists.
		update_win = db.BalanceRecord[-1] if db.BalanceRecord.get(ID=1) else {}
		if update_win:
			update_win.win_status = True if update_win.starting_balance >= (self.balance + bet_amount) else False
		# Update current entry.
		update_bal = db.BalanceRecord()
		update_bal.set(starting_balance=self.balance, bet_amt=bet_amount, bet_ratio=ratio, bet_side=side,
					   favored_side=side if ratio >= 0.5 else teams[f'{side}'], new_balance=int(balance))
		self.balance = int(balance)

	def run(self):
		irc = self.irc
		sock = self.socket
		config = self.config

		global higher, lower, betting_started, time_since_first_bet, bet_team, new_balance, bet_amt, teams

		# Initialize reusable properties.
		totals = {'blue_amt': 0, 'blue_bets': 0, 'red_amt': 0, 'red_bets': 0}
		timers = {'!farm': time(), 'first_bet': time()}
		higher = lower = {}
		bet_complete = False
		betting_started = False
		time_since_first_bet = 0
		teams = {'blue': 'red', 'red': 'blue'}

		while True:
			time_since_collect = int(time() - timers['!farm'])
			time_since_first_bet = int(time() - timers['first_bet'])

			# Check for PING; reply with PONG.
			data = sock.recv(2048).rstrip()
			irc.check_for_ping(data)
			message_dict, channel, message, username = self.check_for_message(irc, data)

			# Check if 121 minutes has passed yet.
			if time_since_collect > 7300:
				irc.send_message(channel, '!farm')
				self.balance = self.check_balance(channel)
				timers['!farm'] = time()

			# Wait until 170 seconds has passed to bet.
			if time_since_first_bet >= 170 and betting_started and not bet_complete:
				# Check which team is in the lead.
				blue = {'name': 'blue', 'amt': totals['blue_amt'], 'bets': totals['blue_bets']}
				red = {'name': 'red', 'amt': totals['red_amt'], 'bets': totals['red_bets']}
				higher, lower = (red, blue) if red['amt'] > blue['amt'] else (blue, red)
				# Bet on the underdog. Or not.
				underdog = lower['name']
				bet_complete, betting_started = self.bet_logic(channel, underdog)
				bet_team = underdog

			# Check if the script is still connected to IRC.
			if len(data) == 0:
				general.pp('Connection was lost, reconnecting...')
				sock = self.irc.get_irc_socket_object

			# Check if most recent data is a message from Twitch chat.
			if username:
				if username != config['username']:
					# Message was sent by @xxsaltbotxx.
					if username == 'xxsaltbotxx':
						# Message contains 'bet complete for'.
						if f'@{self.config["username"]} - Bet complete' in message:
							bet_message = message.split(' - Bet complete for ')[1].split(', ')
							bet_team = bet_message[0].lower()
							bet_ints = bet_message[1].split('.')
							bet_amt = int(bet_ints[0])
							new_balance = int(bet_ints[1].strip('Your new balance is '))
							bet_complete = True
							print("Bet Acknowledged")

						if "Bet complete" in message:
							# This is the first bet of the game.
							if totals['blue_amt'] == 0 and totals['red_amt'] == 0:
								timers['first_bet'] = time()
								time_since_first_bet = 0
								betting_started = True

							# Parse values from xxsaltbotxx's message.
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

							print('Time since first bet: %s s' % time_since_first_bet)
							print(f'Blue: \t{"{:,}".format(totals["blue_amt"])} shrooms, {totals["blue_bets"]} bets')
							print(f'Red: \t{"{:,}".format(totals["red_amt"])} shrooms, {totals["red_bets"]} bets\n')

						# Message contains 'Betting has ended' or over 3 minutes has passed.
						if 'Betting has ended' in message or time_since_first_bet >= 210:
							if totals['blue_amt'] != 0 and totals['red_amt'] != 0:
								if 'name' not in lower:
									lower['name'] = 'UNKNOWN'

								# Logic for SQLite db
								other = teams[f'{bet_team}']
								ratio_calc = int(totals[f'{bet_team}_amt']) / \
											 (int(totals[f'{bet_team}_amt']) + int(totals[f'{other}_amt']))
								entry = self.update_bet(bet_team, bet_amt, new_balance, ratio_calc)

								# Resetting values at the end of betting.
								totals = {'blue_amt': 0, 'blue_bets': 0, 'red_amt': 0, 'red_bets': 0}
								timers['first_bet'] = 0
								time_since_first_bet = 0
								bet_complete = False
								betting_started = False

								print('Betting has ended\n')
								print(f"inserted {entry}")

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
