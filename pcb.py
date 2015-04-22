import math
import sys

UNIT_INCH = 'INCH'
UNIT_MM = 'MM'
unit  = UNIT_MM
convertToMetric = False
IMPERIAL_TO_SANITY_CONVERSION_FACTOR = 25.4
STARTVARRANGE = 100

MARGIN = 0

MINVALUE = 0.0001

format = '{:.5f}'

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
	assert(isinstance(infile, string))
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
	if xindex == xteps-1:
		return (format + '*#{:.0f}').format(yFactor, leftIndex)
	rightIndex = STARTVARRANGE + xindex + 1 + yindex * xsteps
	return (format + '*#{:.0f}+'+format+'*#').format( (xfactor * yFactor), rightIndex, ((1 - xfactor) * yFactor), leftIndex )


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

	xindex = int( math.floor(xlength/xteps) )
	xfactor = (xlength - (xindex * xstep)) / xstep
	yindex = int(math.floor(ylength / ystep))
	yfactor = (ylength - (yindex * ystep)) / ystep

	if xindex >= xsteps:
		raise ValueError()

	if yindex==(ysteps-1):
		return linearInterpolateX(xindex, yindex, xfactor, 1.0 ,xsteps, ysteps)

	if yfactor < 0:
		raise ValueError('yfactor < 0 ')
	if yfactor > 0:
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
		changedZ = "[" + format.format(lastZ) + " + #3 + " + getInterpolatedZ(currentX, currentY, max, xsteps, ysteps)+ "]"
		out.write("Z" + changedZ)
	out.write(newline)

def ModifyGCode(infile, out, maxx, xsteps,  ysteps, maxdistance):
	assert(isinstance(maxx, Rectangle2D))
	