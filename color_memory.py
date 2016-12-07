##=======================================##
## ECE 264 Honors Contract Project       ##
## Code for Colored GDB Memory Dump      ##
##                                       ##
## Written By: Noah Haberland            ##
## PUID:       0027917186                ##
##=======================================##

import gdb
import sys



# returns a string that contains ASCII Color Escape codes
def Color(string, color):
	colors = ['\033[0m' , # none
			  '\033[31m', # red
			  '\033[32m', # green
			  '\033[33m', # yellow
			  '\033[34m', # blue
			  '\033[35m', # magenta 
			  '\033[36m', # teal
			  '\033[37m'] # white

	return colors[color] + string + colors[0]

# encode utf-8 characters
def Draw(string):
	return string.encode('utf-8')

# outputs a box around the given string lines
def DrawBox(maxLength, lines):
	# unicode box characters
	corners = [unichr(0x2554), unichr(0x2557), unichr(0x255A), unichr(0x255D)]
	borders = [unichr(0x2550), unichr(0x2551)]
	
	# draw upper box border
	print Draw(corners[0]+borders[0]*maxLength+corners[1])

	# draw each line with left and right borders
	for line in lines:
		print '%s%-*s%s' %(Draw(borders[1]), maxLength, line, Draw(borders[1]))
	
	# draw bottom box border
	print Draw(corners[2]+borders[0]*maxLength+corners[3])

# change tabs to aligned spaces to proper calculation of line length
def ReplaceTabs(lines):
	# change tabs in each line of assembly code
	for i in range(len(lines)):
		
		# calculate amount to offset replaced tab by
		offset = ''
		charIndex = 24	
		while(lines[i][charIndex] != '>'):
			offset += lines[i][charIndex]
			charIndex += 1

		# replace tabs with correct number of spaces
		lines[i] = lines[i].replace('\t', ' '*(5-len(offset)))
	return lines

# returns the max length of a set of strings
def MaxLength(lines):
	# compare length of each line
	maxLen = len(lines[0])
	for line in lines:
		if(len(line) > maxLen):
			maxLen = len(line)
	return maxLen

# finds the information for the set of variables ccording to varString
def FindVariable(frame, varString):
	# execute gdb command to get output for current variable set
	string = gdb.execute('info %s' % varString, False, True)

	# check of no variables are found
	if(string == 'No locals.\n' or string == 'No arguments.\n'):
		return -1
	
	# otherwise parse string to obtain required data
	else:
		try:
			varNames = [var.split('=')[0][:-1] for var in string.split('\n')[:-1]]
			vars = [frame.read_var(var).__str__().encode() for var in varNames]
			varLocs = [frame.read_var(var).reference_value().__str__().encode()[1:] for var in varNames]
			varSizes = [int(''.join(gdb.execute('p sizeof(%s)' % var, False, True).split()[-1:])) for var in varNames]
			return zip(varNames, vars, varLocs, varSizes)
		except:
			return -2


class Frame:
	
	# initialize frame information
	def __init__(self):
		self.current = gdb.newest_frame()
		self.name = self.current.function()
		self.locals = FindVariable(self.current, 'locals')
		self.args = FindVariable(self.current, 'args')
		self.code = ReplaceTabs(gdb.execute('disas %s' % self.name, False, True).split('\n')[1:-2])
		self.registers = [''] * 3
		self.registers[0] = self.current.read_register('rbp').__str__().encode()
		self.registers[1] = self.current.read_register('rsp').__str__().encode()
		self.registers[2] = self.current.read_register('rip').__str__().encode()
	
	# print assembly code with header and box
	def PrintCode(self):
		maxLength = MaxLength(self.code)
		print "\nAssembly code for %s function:" % self.name
		DrawBox(maxLength, self.code)
	
	# print selected registers with header and box
	def PrintRegisters(self):
		regs = ["Base Pointer: ", "Stack Pointer: ", "Instruction Pointer: "]
		maxLength = MaxLength(['%s%s' % str for str in zip(regs, self.registers)])
		print "\nRegisters:"
		DrawBox(maxLength, ['%-*s%s' % (maxLength-len(self.registers[i]), regs[i], self.registers[i]) for i in range(len(regs))])
	
	# print currenct stack frame with relevant information
	def PrintStack(self):

		print "\nCurrent stack frame:"

		# print warning exceptions to user
		if(self.locals == -2 or self.args == -2):
			print "Error reading local variables or arguments!"
		if(self.locals == -1):
			print "No local variables!"
		if(self.args == -1):
			print "No arguments!"

		# compile relevant variables
		addresses = self.registers[0:2] + [hex(int(self.registers[0], 16)+8)]

		# check for local variables
		checkVars = False
		if(self.locals >= 0):
			addresses += [var[2] for var in self.locals if var[0] != '__PRETTY_FUNCTION__']
			checkVars = True

		# check for arguments
		checkArgs = False
		if(self.args >= 0):
			addresses += [arg[2] for arg in self.args]
			checkArgs = True

		# define range of stack frame
		minAddr = int(min(addresses), 16)
		maxAddr = int(max(addresses), 16)
		
		# variables for properly outputting stack frame
		length = 54
		stack = []
		currAddr = minAddr
		numberOfVars = 0
		offset = 0
		overflow = 0
		addrName = ''
		lastColor = 0

		# create array to store colors for each address
		addrColors = [0] * ((maxAddr - minAddr) + 8 - ((maxAddr - minAddr) % 8))

		# assign color for stored return address
		for j in range(8):
			addrColors[int(self.registers[0], 16) + 8 + j - minAddr] = 3
		
		# assign color for saved base pointer
		for j in range(8):
			addrColors[int(self.registers[0], 16) + j - minAddr] = 4

		# assign color for locals
		if(checkVars):
			for var in self.locals:
				if(var[0] != '__PRETTY_FUNCTION__'):
					for j in range(var[3]):
						addrColors[int(var[2], 16) + j - minAddr] = 1
		
		# assign color for arguments
		if(checkArgs):
			for var in self.args:
				for j in range(var[3]):
					addrColors[int(var[2], 16) + j - minAddr] = 2

		# loop from beginning to end of stack frame and print information
		while currAddr <= maxAddr:
			# output eight memory addresses with implementation of gdb examine function
			string = ''
			string += hex(currAddr)
			for i in range(8):
				string += Color(gdb.execute('x/bx %d' % currAddr, False, True)[15:20].replace('\t', ' '), addrColors[currAddr - minAddr])
				currAddr += 1
			stack.append(string)

			# create new line to parse memory addresses for relevant variables
			string = ''

			# check for stack base pointer
			padding = 0
			if(int(self.registers[0], 16) == currAddr-8):
				string += Draw(unichr(0x2191)) + 'rbp'
				padding = 2

			# check for stack pointer
			if(int(self.registers[1], 16) == currAddr-8):
				string += Draw(unichr(0x2191)) + 'rsp'
				padding = 2

			# special output case when base and stack pointer are equivalent
			if(self.registers[0] == self.registers[1] and string != ''):
				string = string[:4] + ',' + string[5:]
			string += ' '*((14+padding)-len(string))

			# check each address for arguments and locals
			for i in range(8, 0, -1):
				# only check if not currently in range of another variable
				if(offset == 0):

					# check current address for saved return address
					if(currAddr - i == int(self.registers[0], 16)+8):
						addrName = 'return address'
						overflow = len(addrName) - 3
						string += Color(' ' + Draw(unichr(0x25BA)) + addrName[:3], 3) 
						offset = 7
						lastColor = 3

					# check current address for saved base pointer
					elif(currAddr - i == int(self.registers[0], 16)):
						addrName = 'saved rbp'
						overflow = len(addrName) - 3
						string += Color(' ' + Draw(unichr(0x25BA)) + addrName[:3], 4)
						offset = 7
						lastColor = 4

					# check current address for locals 
					elif(checkVars and hex(currAddr - i) in [var[2] for var in self.locals]):
						for var in self.locals:
							if(hex(currAddr - i) == var[2]):
								addrName = var[0]
								overflow = len(var[0]) - 3
								offset = var[3] - 1
								lastColor = 1

								# print variable sized correctly
								if(offset == 0):
									string += Color(' ' + Draw(unichr(0x25BA)) + var[0][:2] + Draw(unichr(0x25C4)), 1)
								else:
									string += Color(' ' + Draw(unichr(0x25BA)) + var[0][:3], 1)
								
								# add extra spaces if required
								if(len(addrName) < 3):
									string += Color(' ' * (3 - len(addrName)), 1)

					# check current address for arguments
					elif(checkArgs and hex(currAddr - i) in [arg[2] for arg in self.args]):
						for arg in self.args:
							if(hex(currAddr - i) == arg[2]):
								addrName = arg[0]
								overflow = len(arg[0]) - 3
								offset = arg[3] - 1
								lastColor = 2

								# print argument sized correctly
								if(offset == 0):
									string += Color(' ' + Draw(unichr(0x25BA)) + arg[0][:2] + Draw(unichr(0x25C4)), 2)
								else:
									string += Color(' ' + Draw(unichr(0x25BA)) + arg[0][:3], 2)
								
								# add extra spaces if required
								if(len(addrName) < 3):
									string += Color(' ' * (3 - len(addrName)), 1)

					# otherwise print blank lines
					else:
						string += ' '*5
				# currently in variable so print required information
				else:
					# fill spaces with blanks or variable name
					for j in range(5):
						
						# if at end of variable range draw closing line
						if(j == 4 and offset == 1):
							string += Color(Draw(unichr(0x25C4)), lastColor)
							addrName = ''
							overflow = 0
							lastColor = 0
						# otherwise draw space or letter if required
						else:
							if(overflow > 0):
								string += Color(addrName[len(addrName) - overflow], lastColor)
								overflow -= 1
							else:
								string += Color(' ', lastColor)

					# decrement counter for variable border
					offset -= 1
							
							
			# add lines to output array
			stack.append(string)

		# draw box around stack frame
		DrawBox(length, stack)

def main():
	
	# ensure disassembly flavor is intel for proper output
	default = gdb.execute('show disassembly-flavor', False, True).split()[4][1:-2]
	gdb.execute('set disassembly-flavor intel')

	# disable pagination for proper output
	gdb.execute('set pagination off')

	# create frame and execute operation
	# try:
	f = Frame()
	f.PrintCode()
	f.PrintRegisters()
	f.PrintStack()
	# except:
	#	print "Could not find stack frame!"

	# restore orignal settings
	gdb.execute('set disassembly-flavor %s' % default)
	gdb.execute('set pagination on')

main()
