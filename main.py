from gpiozero import LED, Button  # wireless GPIO
from gpiozero.pins.pigpio import PiGPIOFactory  # wireless GPIO IP Address
from time import sleep  # sleep
from time import time  # for pinging
import xlrd  # import excel documents
import random
import math  # for rounding floats to ints
import threading
import tkinter as tk  # GUI window stuff
from tkinter import ttk  # GUI labels and stuff
import tkinter.font as tkfont  # get the width of fonts for positioning
#from tkinter import *  # wildcard I know - it's 1 in the morning what do you bloody expect

pi_ip_address = None
ping_during_runtime = True

team_names = []
team_colours = []
button_pins = []
led_pins = []

button_objects = []
led_objects = []

questions = []
answers = []
current_question = 0
show_answer = False

ping_no_response_time = None
time_at_last_ping = 0
ping_input = None

order = []

display = tk.Tk()
control = tk.Tk()
display_width = 0
display_height = 0
event_name = "Gameshow"
font_name = "Arial"

need_to_update_team_gui = False


def config_gui():
    global display, control, display_width, display_height, event_name, font_name, questions, answers,\
        current_question, need_to_update_team_gui

    previous_question = current_question

    display.title("{} - Display".format(event_name))
    display.geometry("{}x{}+0+0".format(display_width, display_height))  # resolution
    font_size = 100
    font_color = "#000000"
    for i in range(0, len(team_names)):
        create_team_gui(i)

    control_width = 150
    control_height = 200
    control.title("{} - Control".format(event_name))
    control.geometry("{}x{}+50+50".format(control_width, control_height))  # resolution
    tk.Button(control, text="Next Team", command=next_team).pack()
    tk.Button(control, text="Clear Teams", command=clear_teams).pack()
    tk.Button(control, text="Next Question", command=next_question).pack()
    tk.Button(control, text="Show Answer", command=display_answer).pack()

    while True:
        # draw the next frames, (required so it doesn't enter the "not responding" state)
        if previous_question != current_question:  # we're onto the next question
            previous_question = current_question
            ttk.Label(
                display,
                text=questions[current_question],
                foreground=font_color,
                background="#ffffff",
                font=(font_name, font_size),
                wraplength=display_width,
                justify="center"
            ).place(x=0, y=0)
        if need_to_update_team_gui:
            need_to_update_team_gui = False
            update_team_gui()

        display.update()
        control.update()


def update_team_gui():
    for i in range(0, len(team_names)):
        create_team_gui(i)


def create_team_gui(index):
    global display_width, display_height, font_name, team_names, display

    text_colour = None
    if len(order) > 0:
        if index == order[0]:
            text_colour = "#ffffff"
        else:
            text_colour = "#000000"
    else:
        text_colour = "#ffffff"

    frame_width = display_width/2
    frame_height = display_height/4

    pos_x = None
    pos_y = None
    if index == 0:
        pos_x = 0
        pos_y = display_height/2
    elif index == 1:
        pos_x = display_width/2
        pos_y = display_height/2
    elif index == 2:
        pos_x = 0
        pos_y = (display_height/2)+frame_height
    elif index == 3:
        pos_x = display_width/2
        pos_y = (display_height/2)+frame_height

    font_object = tkfont.Font(family=font_name, size=100)
    text_width = font_object.measure(team_names[index])  # get the width of the font
    text_pos_x = pos_x + ((frame_width - text_width)/2)  # figure out where to place it for it to be centered
    text_height = font_object.metrics("linespace")  # get the height of the font
    text_pos_y = pos_y + ((frame_height - text_height)/2)  # figure out where to place it for it to be centered

    frame = tk.Frame(
        display,
        bg=team_colours[index],
        height=frame_height,
        width=frame_width
    ).place(x=pos_x, y=pos_y)

    lbl = tk.Label(
        frame,
        text=team_names[index],
        foreground=text_colour,
        background=team_colours[index],
        font=(font_name, 100)
    )
    lbl.place(x=text_pos_x, y=text_pos_y)


def read_data():
    global pi_ip_address, ping_during_runtime, team_names, team_colours, button_pins, led_pins, display_width, \
        display_height, event_name, font_name, questions, answers

    wb = xlrd.open_workbook("./config.xls")  # open the workbook
    sheet = wb.sheet_by_index(0)  # open the first sheet in the workbook
    num_of_teams = sheet.nrows

    for i in range(1, num_of_teams):  # for every team in the Excel document
        team_names.append(sheet.cell_value(i, 0))
        team_colours.append(sheet.cell_value(i, 1))
        button_pins.append(math.floor(sheet.cell_value(i, 2)))
        led_pins.append(math.floor(sheet.cell_value(i, 3)))
        print("Configured the team: {}".format(team_names[len(team_names)-1]))

    pi_ip_address = sheet.cell_value(1, 5)  # F2
    ping_during_runtime = sheet.cell_value(1, 6)  # G2

    if ping_during_runtime:
        global ping_no_response_time
        ping_no_response_time = sheet.cell_value(1, 7)  # 2H

    display_width = math.floor(sheet.cell_value(1, 8))  # 2I
    display_height = math.floor(sheet.cell_value(1, 9))  # 2J
    event_name = sheet.cell_value(1, 10)  # 2K
    font_name = sheet.cell_value(1, 11)  # 2L

    wb = xlrd.open_workbook("./questions.xls")  # open the workbook
    sheet = wb.sheet_by_index(0)  # open the first sheet in the workbook
    num_of_questions = sheet.nrows

    for i in range(1, num_of_questions):
        questions.append(str(sheet.cell_value(i, 0)))
        answers.append(str(sheet.cell_value(i, 1)))


def start_network():
    found_pi = False
    while not found_pi:
        try:
            factory = PiGPIOFactory(host=pi_ip_address)
            found_pi = True
        except OSError:
            print("""Could not find the Pi at IP {}.
            Ensure the Pi is connected and has the appropriate IP address. Trying again...""".format(pi_ip_address))

    print("Found the Pi at {}".format(pi_ip_address))

    for pin in button_pins:
        button_objects.append(Button(pin, pin_factory=factory))
    for pin in led_pins:
        led_objects.append(LED(pin, pin_factory=factory))


def check_ping_status():
    global time_at_last_ping, ping_no_response_time
    already_alerted = True
    while True:
        if time() - time_at_last_ping > ping_no_response_time:  # have we received a ping within ping_no_response_time?
            if not already_alerted:  # have we already alerted the user of this event?
                already_alerted = True
                print("Disconnected from the Pi (no ping)")
        elif already_alerted:  # we've got a connection while we told the user we don't
            already_alerted = False
            print("Connected to the Pi (received a ping)")


def read_buttons():
    global time_at_last_ping

    while True:
        for index, button in enumerate(button_objects):  # for every button
            if button.value:  # if the button is being pressed
                if not show_answer:  # teams are currently to answer the question
                    if index not in order:  # if this button hasn't been pressed already
                        order.append(index)  # add to the list
                        print("Team {} ({}) have pressed their button".format(str(index), team_names[index]))
                        if len(order) == 1:  # if it's the first button pressed for this question
                            change_selected()  # change the GUI and LEDs

        time_at_last_ping = time()  # the while statement will halt if we've lost connection


def change_selected():  # change the selected team
    global order, need_to_update_team_gui
    need_to_update_team_gui = True
    for index, led in enumerate(led_objects):  # for every LED
        if len(order) > 0:
            if index == order[0]:  # turn the LED on if it's the selected team, off if it's not
                led.on()
            else:
                led.off()
        else:  # if there's no team selected, turn on all LEDs
            led.on()


def next_team():
    global order
    if len(order) > 0:
        del order[0]
    change_selected()


def clear_teams():
    global order
    order = []
    change_selected()


def reset_teams():  # turn on all LEDs
    for led in led_objects:
        led.on()


def disable_leds():
    for led in led_objects:
        led.off()


def next_question():
    global current_question, show_answer
    show_answer = False
    current_question += 1
    clear_teams()


def display_answer():
    global show_answer
    show_answer = True
    disable_leds()  # turn off all LEDs when the answer is shown


# Press the green button in the gutter to run the script.
if __name__ == '__main__':

    read_data()  # read config data from excel document
    start_network()  # set up the button and LED pins
    threading.Thread(target=read_buttons).start()  # start the main input loop
    reset_teams()

    if ping_during_runtime:  # start the pinging if applicable
        threading.Thread(target=check_ping_status).start()

    config_gui()


