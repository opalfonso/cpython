import string
from Tkinter import *
import ColorDB

# Load this script into the Tcl interpreter and call it in
# StripWidget.set_color().  This is about as fast as it can be with the
# current _tkinter.c interface, which doesn't support Tcl Objects.
TCLPROC = '''\
proc setcolor {canv colors} {
    set i 1
    foreach c $colors {
        $canv itemconfigure $i -fill $c -outline $c
	incr i
    }
}
'''

# Tcl event types
BTNDOWN = 4
BTNUP = 5
BTNDRAG = 6


def constant(numchips):
    step = 255.0 / (numchips - 1)
    start = 0.0
    seq = []
    while numchips > 0:
	seq.append(int(start))
	start = start + step
	numchips = numchips - 1
    return seq

# red variations, green+blue = cyan constant
def constant_cyan_generator(numchips, red, green, blue):
    seq = constant(numchips)
    return map(None, seq, [green] * numchips, [blue] * numchips)

# green variations, red+blue = magenta constant
def constant_magenta_generator(numchips, red, green, blue):
    seq = constant(numchips)
    return map(None, [red] * numchips, seq, [blue] * numchips)

# blue variations, red+green = yellow constant
def constant_yellow_generator(numchips, red, green, blue):
    seq = constant(numchips)
    return map(None, [red] * numchips, [green] * numchips, seq)




class LeftArrow:
    _ARROWWIDTH = 30
    _ARROWHEIGHT = 15
    _YOFFSET = 13
    _TEXTYOFFSET = 1
    _TAG = ('leftarrow',)

    def __init__(self, canvas, x):
	self._canvas = canvas
	self.__arrow, self.__text = self._create(x)
	self.move_to(x)

    def _create(self, x):
	arrow = self._canvas.create_line(
	    x, self._ARROWHEIGHT + self._YOFFSET,
	    x, self._YOFFSET,
	    x + self._ARROWWIDTH, self._YOFFSET,
	    arrow='first',
	    width=3.0,
	    tags=self._TAG)
	text = self._canvas.create_text(
	    x + self._ARROWWIDTH + 13,
	    self._ARROWHEIGHT - self._TEXTYOFFSET,
	    tags=self._TAG,
	    text='128')
	return arrow, text

    def _x(self):
	coords = self._canvas.coords(self._TAG)
	assert coords
	return coords[0]

    def move_to(self, x):
	deltax = x - self._x()
	self._canvas.move(self._TAG, deltax, 0)

    def set_text(self, text):
	self._canvas.itemconfigure(self.__text, text=text)


class RightArrow(LeftArrow):
    _TAG = ('rightarrow',)

    def _create(self, x):
	arrow = self._canvas.create_line(
	    x, self._YOFFSET,
	    x + self._ARROWWIDTH, self._YOFFSET,
	    x + self._ARROWWIDTH, self._ARROWHEIGHT + self._YOFFSET,
	    arrow='last',
	    width=3.0,
	    tags=self._TAG)
	text = self._canvas.create_text(
	    x - self._ARROWWIDTH + 15,		  # TBD: kludge
	    self._ARROWHEIGHT - self._TEXTYOFFSET,
	    text='128',
	    tags=self._TAG)
	return arrow, text

    def _x(self):
	coords = self._canvas.bbox(self._TAG)
	assert coords
	return coords[2] - 6			  # TBD: kludge



class StripWidget:
    _CHIPHEIGHT = 50
    _CHIPWIDTH = 10
    _NUMCHIPS = 40

    def __init__(self, switchboard,
                 parent     = None,
                 chipwidth  = _CHIPWIDTH,
                 chipheight = _CHIPHEIGHT,
                 numchips   = _NUMCHIPS,
                 generator  = None,
                 axis       = None,
                 label      = ''):
        # instance variables
	self.__generator = generator
	self.__axis = axis
        self.__numchips = numchips
	assert self.__axis in (0, 1, 2)
	self.__update_while_dragging = 0
        # the last chip selected
        self.__lastchip = None
        self.__sb = switchboard
        
	canvaswidth = numchips * (chipwidth + 1)
	canvasheight = chipheight + 43		  # TBD: Kludge

	# create the canvas and pack it
	canvas = self.__canvas = Canvas(
	    parent,
	    width=canvaswidth,
	    height=canvasheight,
## 	    borderwidth=2,
## 	    relief=GROOVE
	    )

	canvas.pack()
	canvas.bind('<ButtonPress-1>', self.__select_chip)
	canvas.bind('<ButtonRelease-1>', self.__select_chip)
	canvas.bind('<B1-Motion>', self.__select_chip)

	# Load a proc into the Tcl interpreter.  This is used in the
	# set_color() method to speed up setting the chip colors.
	canvas.tk.eval(TCLPROC)

	# create the color strip
	chips = self.__chips = []
	x = 1
	y = 30
	tags = ('chip',)
	for c in range(self.__numchips):
	    color = 'grey'
	    rect = canvas.create_rectangle(
		x, y, x+chipwidth, y+chipheight,
		fill=color, outline=color,
		tags=tags)
	    x = x + chipwidth + 1		  # for outline
	    chips.append(color)

	# create the strip label
	self.__label = canvas.create_text(
	    3, y + chipheight + 8,
	    text=label,
	    anchor=W)

	# create the arrow and text item
	chipx = self.__arrow_x(0)
	self.__leftarrow = LeftArrow(canvas, chipx)

	chipx = self.__arrow_x(len(chips) - 1)
	self.__rightarrow = RightArrow(canvas, chipx)

    def __arrow_x(self, chipnum):
	coords = self.__canvas.coords(chipnum+1)
	assert coords
	x0, y0, x1, y1 = coords
	return (x1 + x0) / 2.0

    # Invoked when one of the chips is clicked.  This should just tell the
    # switchboard to set the color on all the output components
    def __select_chip(self, event=None):
        x = event.x
        y = event.y
        canvas = self.__canvas
        chip = canvas.find_overlapping(x, y, x, y)
        if chip and (1 <= chip[0] <= self.__numchips):
            color = self.__chips[chip[0]-1]
            red, green, blue = ColorDB.rrggbb_to_triplet(color)
            etype = int(event.type)
            if (etype == BTNUP or self.__update_while_dragging):
                # update everyone
                self.__sb.update_views(red, green, blue)
            else:
                # just track the arrows
                self.__trackarrow(chip[0], (red, green, blue))

    def __trackarrow(self, chip, rgbtuple):
        # invert the last chip
        if self.__lastchip is not None:
            color = self.__canvas.itemcget(self.__lastchip, 'fill')
            self.__canvas.itemconfigure(self.__lastchip, outline=color)
        self.__lastchip = chip
	# get the arrow's text
	coloraxis = rgbtuple[self.__axis]
	text = repr(coloraxis)
	# move the arrow, and set it's text
	if coloraxis <= 128:
	    # use the left arrow
	    self.__leftarrow.set_text(text)
	    self.__leftarrow.move_to(self.__arrow_x(chip-1))
	    self.__rightarrow.move_to(-100)
	else:
	    # use the right arrow
	    self.__rightarrow.set_text(text)
	    self.__rightarrow.move_to(self.__arrow_x(chip-1))
	    self.__leftarrow.move_to(-100)
	# and set the chip's outline
        brightness = ColorDB.triplet_to_brightness(rgbtuple)
	if brightness <= 0.5:
	    outline = 'white'
	else:
	    outline = 'black'
	self.__canvas.itemconfigure(chip, outline=outline)


    def update_yourself(self, red, green, blue):
	assert self.__generator
	i = 1
	chip = 0
	chips = self.__chips = []
	tclcmd = []
	tk = self.__canvas.tk
        # get the red, green, and blue components for all chips
        for t in self.__generator(self.__numchips, red, green, blue):
            rrggbb = ColorDB.triplet_to_rrggbb(t)
            chips.append(rrggbb)
            tred, tgreen, tblue = t
            if tred <= red and tgreen <= green and tblue <= blue:
                chip = i
            i = i + 1
        # call the raw tcl script
        colors = string.join(chips)
        tk.eval('setcolor %s {%s}' % (self.__canvas._w, colors))
        # move the arrows around
        self.__trackarrow(chip, (red, green, blue))

    def set_update_while_dragging(self, flag):
	self.__update_while_dragging = flag



class StripViewer:
    def __init__(self, switchboard, parent=None):
        self.__sb = switchboard
        self.__reds = StripWidget(switchboard, parent,
                                  generator=constant_cyan_generator,
                                  axis=0,
                                  label='Red Variations')

        self.__greens = StripWidget(switchboard, parent,
                                    generator=constant_magenta_generator,
                                    axis=1,
                                    label='Green Variations')

        self.__blues = StripWidget(switchboard, parent,
                                   generator=constant_yellow_generator,
                                   axis=2,
                                   label='Blue Variations')

    def update_yourself(self, red, green, blue):
        self.__reds.update_yourself(red, green, blue)
        self.__greens.update_yourself(red, green, blue)
        self.__blues.update_yourself(red, green, blue)
