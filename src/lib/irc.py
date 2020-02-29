import re
import socket
import sys
from time import sleep
from src.lib.functions_general import *


class irc(object):
	def __init__(self, config):
		self.config = config
		self.sock = None

	@staticmethod
	def check_for_message(data):
		data = data.decode('utf-8')
		if re.match(
				r'^:[a-zA-Z0-9_]+![a-zA-Z0-9_]+@[a-zA-Z0-9_]+(\.tmi\.twitch\.tv|\.testserver\.local) PRIVMSG #[a-zA-Z0-9_]+ :.+$',
				data):
			return True

	@staticmethod
	def check_is_command(message, valid_commands):
		for command in valid_commands:
			if command == message:
				return True

	@staticmethod
	def check_for_connected(data):
		if re.match(r'^:.+ 001 .+ :connected to TMI$', data):
			return True

	def check_for_ping(self, data):
		if data[:4] == "PING":
			self.sock.send('PONG')

	@staticmethod
	def get_message(data):
		data = data.decode('utf-8')
		return {
			'channel': re.findall(r'^:.+![a-zA-Z0-9_]+@[a-zA-Z0-9_]+.+ PRIVMSG (.*?) :', data)[0],
			'username': re.findall(r'^:([a-zA-Z0-9_]+)!', data)[0],
			'message': re.findall(r'PRIVMSG #[a-zA-Z0-9_]+ :(.+)', data)[0]
		}

	@staticmethod
	def check_login_status(data):
		data = data.decode('utf-8')
		if re.match(r'^:(testserver\.local|tmi\.twitch\.tv) NOTICE \* :Login unsuccessful\r\n$', data):
			return False
		else:
			return True

	def send_message(self, channel, message):
		# Loop each send 3 times in case the first one or two fail.
		for i in range(1):
			# Wait 0.5 second, just in case a message was sent a moment ago.
			sleep(0.5)
			self.sock.send(f'PRIVMSG {channel} :{message}\r\n'.encode())

	@property
	def get_irc_socket_object(self):
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		
		sock.settimeout(10)

		self.sock = sock

		try:
			sock.connect(('irc.chat.twitch.tv', 6667))
		except:
			sys.exit()

		sock.settimeout(None)

		sock.send(f'USER {self.config["username"]}\r\n'.encode())
		sock.send(f'PASS {self.config["oauth_password"]}\r\n'.encode())
		sock.send(f'NICK {self.config["username"]}\r\n'.encode())

		data = sock.recv(1024)
		if self.check_login_status(data):
			pass
		else:
			sys.exit()

		self.join_channels(self.channels_to_string(self.config['channels']))

		return sock

	@staticmethod
	def channels_to_string(channel_list):
		return ','.join(channel_list)

	def join_channels(self, channels):
		self.sock.send(f'JOIN {channels}\r\n'.encode())
		pp('Connection established.')

	def leave_channels(self, channels):
		pp('Leaving channels %s,' % channels)
		self.sock.send(f'PART {channels}\r\n'.encode())
		pp('Left channels.')
