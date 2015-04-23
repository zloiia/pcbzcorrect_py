import math
import sys
import os
import cStringIO

UNIT_INCH = 'INCH'
UNIT_MM = 'MM'
unit  = UNIT_MM
convertToMetric = False
IMPERIAL_TO_SANITY_CONVERSION_FACTOR = 25.4
STARTVARRANGE = 100
mach3 = True

lineend = '\n'

MARGIN = 0

MINVALUE = 0.0001

format = '{:.5f}'

xsteps = 5
ysteps = 5


class Rectangle2D:
	_minX=0
	_maxX=0
	_minY=0
	_maxY=0
	def __init__(self, minx, miny, w, h):
		self._minX=minx
		self._minY=miny
		self._maxX=minx + w 
		self._maxY=miny + h

	@property
	def width(self):
		return abs(self._minX - self._maxX)

	@property
	def height(self):
		return abs(self._minY - self._maxY)

	@property
	def minY(self):
		return self._minY

	@property
	def maxY(self):
		return self._maxY

	@property
	def minX(self):
		return self._minX

	@property
	def maxX(self):
		return self._maxX


def distance(x1, y1,  x2, y2):
	xdist = x2 - x1
	ydist = y2 - y1
	return math.sqrt(xdist * xdist + ydist * ydist)


def getXLocation(xindex, xsteps, dimensions):
	assert(isinstance(dimensions, Rectangle2D))
	stepLength = dimensions.width / (xsteps - 1)
	return dimensions.minX + stepLength * xindex

def getYLocation(yindex, ysteps, dimensions):
	assert(isinstance(dimensions, Rectangle2D))
	stepLength = dimensions.height / (ysteps - 1)
	return dimensions.minY + stepLength * yindex

def getMaxDimensions(infile, margins):
	#assert(isinstance(infile, str))
	global unit
	maxX = sys.float_info.min
	minX = sys.float_info.max
	maxY = sys.float_info.min
	minY = sys.float_info.max
	for line in infile:
		line = line.upper()
		if line.startswith('G20'):
			unit = UNIT_INCH
		if line.startswith('G21'):
			unit = UNIT_MM
		tokens = line.split(' ')
		for token in tokens:
			if token.startswith('X'):
				value = float(token[1:])
				maxX = max(maxX, value)
				minX = min(minX, value)
			else:
				if token.startswith('Y'):
					value = float(token[1:])
					maxY = max(maxY, value)
					minY = min(minY, value)
	marginX = (maxX-minX)* margins
	marginY =  (maxY-minY)* margins
	minXmargin = minX + marginX
	maxXmargin = maxX - marginX
	minYmargin = minY + marginY
	maxYmargin = maxY - marginY
	return Rectangle2D(minXmargin, minYmargin, maxXmargin - minXmargin, maxYmargin - minYmargin)

def convert(distance):
	distance = float(distance)
	if convertToMetric and unit==UNIT_INCH:
		return distance * IMPERIAL_TO_SANITY_CONVERSION_FACTOR
	return distance


def linearInterpolateX(xindex, yindex, xfactor, yFactor, xsteps, ysteps):
	if xfactor<0:
		raise ValueError("xfactor < 0")
	if xfactor > 1:
		raise ValueError("xfactor > 1")
	if (xindex>=xsteps):
		raise ValueError("xindex (=%d) >= xteps(=%d)"%(xindex, xsteps))
	if (yindex>=ysteps):
		raise ValueError("yindex (=%d) >= yteps(=%d)"%(yindex, ysteps))
	leftIndex = STARTVARRANGE + xindex + yindex * xsteps
	if xindex == xsteps-1:
		return (format + '*#{:.0f}').format(yFactor, leftIndex)
	rightIndex = STARTVARRANGE + xindex + 1 + yindex * xsteps
	return format.format(xfactor * yFactor) + " * " + "#" + str(rightIndex) + ' + ' + format.format((1 - xfactor) * yFactor) + ' * ' + '#' + str(leftIndex)
	#return (format + '*#{:.0f}+'+format+'*#').format( (xfactor * yFactor), rightIndex, ((1 - xfactor) * yFactor), leftIndex )


def getInterpolatedZ(lastX, lastY,  maxx,  xsteps, ysteps):
	assert(isinstance(maxx,Rectangle2D))
	lastX = float(lastX)
	lastY = float(lastY)
	xsteps = int(xsteps)
	ysteps = int(ysteps)
	xlength = lastX - maxx.minX
	ylength = lastY - maxx.minY
	xstep = maxx.width / (xsteps - 1)
	ystep = maxx.height / (ysteps - 1)

	if abs(xlength) < MINVALUE:
		xlength = 0

	if abs(ylength) < MINVALUE:
		ylength = 0

	if (xlength<0):
		raise ValueError('')
	else:
		if xlength > maxx.width:
			raise ValueError()

	if ylength < 0:
		raise ValueError()
	else:
		if ylength > maxx.height:
			raise ValueError()

	xindex = int( math.floor(xlength/xstep) )
	xfactor = (xlength - (xindex * xstep)) / xstep
	yindex = int(math.floor(ylength / ystep))
	yfactor = (ylength - (yindex * ystep)) / ystep

	if xindex >= xsteps:
		raise ValueError()

	if yindex==(ysteps-1):
		return linearInterpolateX(xindex, yindex, xfactor, 1.0 ,xsteps, ysteps)

	if yfactor < 0:
		raise ValueError('yfactor < 0 ')
	if yfactor > 1:
		raise ValueError('yfactor > 1')

	x1 = linearInterpolateX(xindex, yindex, xfactor, 1-yfactor ,xsteps, ysteps)
	x2 = linearInterpolateX(xindex, yindex + 1, xfactor, yfactor ,xsteps, ysteps)

	return x1 + " + "+ x2

def writeGCodeLine(maxx, xsteps, ysteps, out,  newline, currentX, currentY, lastZ, outline,  found, foundZ):
	if found or foundZ:
		changedZ = format.format(lastZ)
		xstr = ""
		ystr = ""
		if (currentX is not None) and (currentY is not None):
			changedZ =  "[" + changedZ + " + #3 + " + getInterpolatedZ(currentX, currentY, maxx, xsteps, ysteps) + "]"
			xstr = format.format(currentX)
			ystr = format.format(currentY)
		formated = outline.format( xstr, ystr, changedZ )
		out.write(formated)
	else:
		out.write(outline)

	if found and not foundZ and (lastZ < sys.float_info.max):
		changedZ = "[" + format.format(lastZ) + " + #3 + " + getInterpolatedZ(currentX, currentY, maxx, xsteps, ysteps)+ "]"
		out.write("Z" + changedZ)
	out.write(newline)

def ModifyGCode(infile, out, maxx, xsteps,  ysteps, maxdistance):
	assert(isinstance(maxx, Rectangle2D))
	newline = lineend
	currentX = None
	currentY = None
	oldX = None
	oldY = None
	lastZ = sys.float_info.max
	with open(infile, 'r') as inff:
		for line in inff:
			line = line.replace('\n','')
			tokens = line.split(' ')
			outline = ''
			found = False
			foundZ = False
			for token in tokens:
				if token=='\n': continue
				if token.startswith('G21') and convertToMetric:
					token = token.replace('G21','G20')
				else:
					if token.startswith("X"):
						oldX = currentX
						currentX = convert(float(token[1:]))
						token = 'X{0}'
						found = True
					else:
						if token.startswith("Y"):
							oldY = currentY
							currentY = convert(float(token[1:]))
							token = 'Y{1}'
							found = True
						else:
							if token.startswith('F') and convertToMetric:
								oldY = currentY
								currentSpeed = convert(float(token[1:]))
								token = 'F' + format.format(currentSpeed)
							else:
								if token.startswith('Z'):
									lastZ = convert(float(token[1:]))
									if currentX is None and currentY is None:
										if lastZ <0:
											pass
											## ERRRROR
										else:
											token = 'Z{2}'
									foundZ = True
				outline += token + ' '
				if len(outline)>100:
					##log error
					exit(-2)
			if (lastZ >0) or (oldX is None) or (oldY is None) or not found or (distance(currentX, currentY, oldX, oldY) < maxdistance):
				writeGCodeLine(maxx, xsteps, ysteps, out, newline, currentX,currentY, lastZ, outline, found, foundZ)
			else:
				count = int(math.ceil(distance(currentX, currentY, oldX, oldY) / maxdistance))
				out.write("( BROKEN UP INTO " + count + " MOVEMENTS )")
				out.write(newline)
				xdist = currentX - oldX
				ydist = currentY - oldY
				for i in range(1,count+1):
					xinterpolated = oldX + i * xdist/count
					yinterpolated = oldY + i * ydist/count
					writeGCodeLine(maxx, xsteps, ysteps, out, newline, xinterpolated,yinterpolated, lastZ, outline, found, foundZ)

def doWork(iinf, safe_height = 50, travel_height = 10, z_offset = 0, probe_feedrate = 400, probe_depth = -10):
	out = cStringIO.StringIO()
	with open(iinf, 'r') as infile:
		maxx = getMaxDimensions(infile, MARGIN)
		ext = os.path.splitext(iinf)[1]
		#with open(iinf[:-1*len(ext)] + "_zprobed" + ext, 'r') as out:
		
		newline = lineend
		maxdist = distance(maxx.minX, maxx.minY, maxx.maxX, maxx.maxY / 6)
		out.write("(Things you can change:)"); out.write(newline)
		if unit == UNIT_MM:
			out.write("#1="+str(safe_height)+"		(Safe height)");out.write(newline)
			out.write("#2="+str(travel_height)+"		(Travel height)");out.write(newline)
			out.write("#3="+str(z_offset)+" 		(Z offset)");out.write(newline)
			out.write("#4="+str(probe_depth)+"		(Probe depth)");out.write(newline)
			out.write("#5="+str(probe_feedrate)+"		(Probe plunge feedrate)");out.write(newline)
			out.write("");out.write(newline)
			out.write("(Things you should not change:)");out.write(newline)
			out.write("G21		(mm)");out.write(newline)
		else:
			out.write("#1=1 		(Safe height)");out.write(newline)
			out.write("#2=0.5		    (Travel height)");out.write(newline)
			out.write("#3=0 		(Z offset)");out.write(newline)
			out.write("#4=-1		(Probe depth)");out.write(newline)
			out.write("#5=25		(Probe plunge feedrate)");out.write(newline)
			out.write("");out.write(newline)
			out.write("(Things you should not change:)");out.write(newline)
			out.write("G20		(inch)");out.write(newline)
		out.write("G90		(Abs coords)");out.write(newline)
		out.write("");out.write(newline)
		out.write("M05		(Stop Motor)");out.write(newline)
		out.write("G00 Z[#1]       (Safe height)");out.write(newline)
		out.write("G00 X0 Y0       (.. on the ranch)");out.write(newline)
		out.write("");out.write(newline)

		for xi in range(xsteps):
			yiStart = 0
			yiStep = 1
			if xi %2 == 1:
				yiStart = ysteps - 1
				yiStep = -1
			yi = yiStart
			while yi < ysteps and yi >=0:
				arrayIndex = STARTVARRANGE + xi + xsteps*yi
				xLocation = getXLocation(xi, xsteps, maxx)
				yLocation = getYLocation(yi, ysteps, maxx)
				out.write("(PROBE[" + str(xi) + "," + str(yi) + "] " + format.format(xLocation) + " " + format.format(yLocation) + " -> " + str(arrayIndex) + ")");out.write(newline)
				out.write("G00 X" + format.format(xLocation) + " Y" + format.format(yLocation) + " Z[#2]");out.write(newline) 

				if mach3:
					out.write("G31 Z[#4] F[#5]");out.write(newline)
					out.write("#" + str(arrayIndex) + "=#2002");out.write(newline)
				else:
					out.write("G38.2 Z[#4] F[#5]");out.write(newline)
					out.write("#" + str(arrayIndex) + "=#5063");out.write(newline)
				out.write("G00 Z[#2]");out.write(newline)
				yi += yiStep
		out.write("( PROBING DONE, remove probe now, then press CYCLE START)");out.write(newline)
		out.write("M0");out.write(newline)

	ModifyGCode(iinf, out, maxx, xsteps, ysteps, maxdist)

	return out.getvalue()