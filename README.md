Salty Teemo Betting Bot
==========

This is a fork of the Salty Teemo twitch-bot made by knakamura13, https://github.com/knakamura13/salty-teemo-betting-bot
Which itself was a fork of the twitch-bot made by aidanrwt: https://github.com/aidanrwt/twitch-bot
It is a simple Twitch chat/irc bot written in Python 3.8, modified to interact with the Salty Teemo channel.

Getting Started
============
* Ensure your system has Python 3.8 installed: `python --version`
* Install the `requests` package: `pip install requests`
* Also install the `pony.orm` package for SQLite management: `pip install pony`
* Clone the Git repository: `git clone https://github.com/BuckeyeSundae/salty-teemo-betting-bot`
* Replace all of the placeholders in `src/config/config.py` with your own username, oauth token, channels, etc.
* Make the serve.py script executable: `chmod +x serve.py`
* Run the serve.py script: `./serve.py` or `python serve.py`

Adding your own commands
========================

Custom commands should be added to: `lib/command_headers.py`. 
These are commands that the bot will listen for and respond to accordingly.
There are examples already in `command_headers.py` for you to look at.

#### Simple Commands
The `limit` parameter is the minimum time between uses that you want to allow for that command.
If your command is only going to return a string, such as the `!hello` command, don't include the `argc` parameter. 
Place the string you wish to be returned to the user in the `return` parameter. This is what the bot will type in the Twitch chat for everyone to see.

```python
'!hello': {
	'limit': 10,
	'return': 'Hello from the Python code!'
}
```

#### Complex Commands (functions)
Let's say we want a command which will take two arguments and perform logic based on the arguments. 
The command is `!rand` and it will take a `minimum` and `maximum` argument. We will limit this command to be used once every 10 seconds.

This command is already created for you:

```python
'!rand': {
	'limit': 10,
	'argc': 2,
	'return': 'command'
}
```

And then in `lib/commands/_rand.py`, you will find the following: 

```python
import random

def _rand(args):
	min = int(args[0])
	max = int(args[1])
	
	try:
		return '%s' % random.randint(min, max)
	except ValueError:
		return '!random <min> <max> (use full integers)'
	except:
		return '!random <min> <max>'
```

Now, if a user types `!rand 5 10` into the Twitch chat, the bot will respond with a number between 5 and 10.

Notice that both the filename and the function name are `_rand`. Each command should have a new file named `_commandName.py` with a single function `_commandName(args)`, where `commandName` is the phrase that will trigger the command from Twitch chat, i.e. `!commandName`. The underscores ensure that the function name will not overwrite existing python functions/methods.


Betting in Salty Teemo
======================

The code that determines which team to bet on and how many mushrooms to bet is the following:
```
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
```
This method contains the objects used in the normal logic. It will create a random bet between 500-1500 and randomly choose a side if the total bets are nearly even between the sides (between .4 and .6). If the ratio is not even, the bet will be a rnadom integer between 1000-3000 on the side expected to win.


Saving Bet Information
===============================
The logic for updating (or creating) the SQLite database is imported into bot.by from src/lib/sql_table.py. This file contains the structure of the database to be built, which at the moment is a single table named "BalanceRecord". This class is imported into bot.py in the update_bet method call (lines 48-69). It updates the previous record with its guess about who won that game, based on starting balance math. It then inserts a new row with the information about the most recent bet at the conclusion of betting.
