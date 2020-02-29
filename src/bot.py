from time import time
import random
import src.lib.irc as irc_
import src.lib.functions_general as general
import src.lib.functions_commands as commands


class Main:
	def __init__(self, config):
		self.config = config
		self.irc = irc_.irc(config)
		self.socket = self.irc.get_irc_socket_object

	def run(self):
		irc = self.irc
		sock = self.socket
		config = self.config

		global higher, lower, betting_started, time_since_first_bet

		# Initialize reusable properties.
		totals = {'blue_amt': 0, 'blue_bets': 0, 'red_amt': 0, 'red_bets': 0}
		timers = {'!collect': time(), 'first_bet': time()}
		higher = lower = {}
		bet_complete = False
		betting_started = False
		time_since_first_bet = 0

		while True:
			time_since_collect = int(time() - timers['!collect'])
			time_since_first_bet = int(time() - timers['first_bet'])

			# Check if 60 minutes has passed yet.
			if time_since_collect > 3600:
				irc.send_message(channel, '!collect')
				timers['!collect'] = time()

			# Wait until 170 seconds has passed to bet.
			if time_since_first_bet >= 170 and betting_started and not bet_complete:
				# Check which team is in the lead.
				blue = {'name': 'blue', 'amt': totals['blue_amt'], 'bets': totals['blue_bets']}
				red = {'name': 'red', 'amt': totals['red_amt'], 'bets': totals['red_bets']}
				if red['amt'] > blue['amt']:
					higher = red
					lower = blue
				else:
					higher = blue
					lower = red

				# Bet on the underdog.
				underdog = lower['name']

				# Bet 1000 mushrooms
				bet = random.randint(500, 1500)

				# Send the message and record the bet.
				irc.send_message(channel, f'!{underdog} {bet}')
				print(f'Bet complete: !{underdog} {bet}\n')
				bet_complete = True
				betting_started = False

			data = sock.recv(2048).rstrip()

			# Check if the script is still connected to IRC.
			if len(data) == 0:
				general.pp('Connection was lost, reconnecting...')
				sock = self.irc.get_irc_socket_object

			# Check for PING; reply with PONG.
			irc.check_for_ping(data)

			# Check if most recent data is a message from Twitch chat.
			if irc.check_for_message(data):
				message_dict = irc.get_message(data)
				channel = message_dict['channel']
				message = message_dict['message']
				username = message_dict['username']

				#######################################
				# Handle messages sent by other users #
				#######################################

				if username != config['username']:
					# Message was sent by @xxsaltbotxx.
					if username == 'xxsaltbotxx':
						# Message contains 'bet complete for'.
						if 'Bet complete' in message:
							# This is the first bet of the game.
							if totals['blue_amt'] == 0 and totals['red_amt'] == 0:
								timers['first_bet'] = time()
								time_since_first_bet = 0
								betting_started = True

							# Parse values from xxsaltbotxx's message.
							split = message.split(' - Bet complete for ')[1].split(', ')
							team = split[0].lower()				# Team name.
							amt = int(split[1].split('.')[0])	# Bet amount.

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

								# Set all globals back to zero.
								totals = {'blue_amt': 0, 'blue_bets': 0, 'red_amt': 0, 'red_bets': 0}
								timers['first_bet'] = 0
								time_since_first_bet = 0
								bet_complete = False
								betting_started = False

								print('Betting has ended\n')

				########################################
				# Handle messages sent by your account #
				########################################

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
									general.pbot(f'Command is on cooldown. ({command}) ({username}) ({commands.get_cooldown_remaining(command, channel)}s remaining)', channel)
								else:
									# Command (function) is not on cooldown, so send a message to Twitch chat.
									general.pbot(f'({command}) ({username})', channel)
									result = commands.pass_to_function(command, args)

									if result:
										# Function returned a valid result.
										general.pbot(result, channel)
										irc.send_message(channel, result)
										commands.update_last_used(command, channel)

						# Command is not a function and has no arguments (i.e. a simple command with a simple response, such as "!test").
						else:
							if commands.is_on_cooldown(command, channel):
								general.pbot(f'Command is on cooldown. ({command}) ({username}) ({commands.get_cooldown_remaining(command, channel)}s remaining)', channel)
							elif commands.check_has_return(command):
								# Command is not on cooldown, so send a message to Twitch chat.
								general.pbot(f'({command}) ({username})', channel)
								res = commands.get_return(command)
								general.pbot(res, channel)
								irc.send_message(channel, res)
								commands.update_last_used(command, channel)
