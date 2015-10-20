#!/usr/bin/env python

"""
This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
"""

import sys
import os
import time
import subprocess
import getpass
from ctypes import c_char_p, cdll

import battery_values
import battery_notifications

try:
    import argparse
except ImportError:
    print("!!! Unsupported python version !!!")
    print("Supported python version are: >=2.7 and >=3.2")
    print("Your python version is: %s.%s.%s" % (sys.version_info[0], sys.version_info[1], sys.version_info[2]))
    print("Please install argparse from: https://pypi.python.org/pypi/argparse")
    exit(0)

PROGRAM_NAME = "Battmon"
VERSION = '0.5-20102015'
DESCRIPTION = ('Simple battery monitoring program written in python especially for tiling window managers '
               'like awesome, dwm, xmonad.')
EPILOG = ('If you want change default screenlock command, edit DEFAULT_SCREEN_LOCK_COMMAND variable in battmon.py'
          ' or change it by parsing your screenlock command througth -lp argument in command line,'
          ' when you use this argument remember to surround whole your screenlock command with quotes.'
          ' Sound file is search by default in the same path where battmon was started,'
          ' you can change this by parsing your path to sound file using -sp argument in command line without quotes.')

AUTHOR = 'nictki'
AUTHOR_EMAIL = 'nictki@gmail.com'
URL = 'https://github.com/nictki/Battmon/tree/master/Battmon'
LICENSE = "GNU GPLv2+"

# get current user name
USER = getpass.getuser()

# get Battmon root directory
PROGRAM_PATH = os.path.dirname(os.path.realpath(__file__))

# path's for external things
EXTRA_PROGRAMS_PATH = ['/usr/bin/',
                       '/usr/local/bin/',
                       '/bin/',
                       '/usr/sbin/',
                       '/usr/libexec/',
                       '/sbin/',
                       '/usr/share/sounds/',
                       PROGRAM_PATH + "/bin/"]

# default sound file path
DEFAULT_SOUND_FILE_PATH = PROGRAM_PATH + "/sounds/info.wav"

# default play command
DEFAULT_PLAYER_COMMAND = 'play'
MAX_SOUND_VOLUME_LEVEL = 17

# screenlock commands first found in this list will be used as default
SCREEN_LOCK_COMMANDS = ['physlock -d -u ' + USER, 'i3lock -c 000000', 'xtrlock -b', 'xscreensaver-command -lock']
# default screen lock command, default empty
# this value can be hardcoded as well eg:
# DEFAULT_SCREEN_LOCK_COMMAND = 'xscreensaver-command -lock'
# but will be overwrite when command line parameter was given
DEFAULT_SCREEN_LOCK_COMMAND = 'i3lock -c 000000'


# main class
class MainRun(object):
    def __init__(self, **kwargs):
        # parameters
        self.__debug = kwargs.get("debug")
        self.__test = kwargs.get("test")
        self.__foreground = kwargs.get("foreground")
        self.__more_then_one_instance = kwargs.get("more_then_one_instance")
        self.__screenlock_command = kwargs.get("lock_command")
        self.__disable_notifications = kwargs.get("disable_notifications")
        self.__show_only_critical = kwargs.get("critical")
        self.__sound_file = kwargs.get("sound_file")
        self.__play_sound = kwargs.get("play_sound")
        self.__sound_volume = kwargs.get("sound_volume")
        self.__timeout = kwargs.get("timeout") * 1000
        self.__battery_update_timeout = kwargs.get("battery_update_timeout")
        self.__battery_low_value = kwargs.get("battery_low_value")
        self.__battery_critical_value = kwargs.get("battery_critical_value")
        self.__battery_minimal_value = kwargs.get("battery_minimal_value")
        self.__minimal_battery_level_command = kwargs.get("minimal_battery_level_command")
        self.__set_no_battery_remainder = kwargs.get("set_no_battery_remainder")
        self.__disable_startup_notifications = kwargs.get("disable_startup_notifications")

        # external programs
        self.__current_program_path = ''
        self.__found_notify_send_command = ''
        self.__sound_player = ''
        self.__sound_command = ''

        # minimal battery command in short for notifying . eg 'HIBERNATE'
        self.__short_minimal_battery_command = ''

        # initialize BatteryValues class instance
        self.__battery_values = battery_values.BatteryValues()

        # check if we can send notifications via notify-send
        self.__check_notify_send()
        # check play command (sox) and if file sounds are in PATH's
        self.__check_play()
        self.__set_sound_file_and_volume()

        # check if program already running otherwise set name
        if not self.__more_then_one_instance:
            self.__check_if_battmon_already_running()

        # set Battmon process name
        self.__set_proc_name(PROGRAM_NAME)

        # set default arguments for debug
        if self.__debug:
            self.__disable_startup_notifications = False
            self.__foreground = True
            self.__show_only_critical = False
            self.__disable_notifications = False

        # set argument for startup notifications if notification is disabled
        if self.__disable_notifications:
            self.__disable_startup_notifications = True

        # set lock and min battery command
        self.__set_lock_command()
        self.__set_minimal_battery_level_command()

        # initialize notification
        self.notification = battery_notifications.BatteryNotifications(self.__disable_notifications,
                                                                       self.__found_notify_send_command,
                                                                       self.__show_only_critical, self.__play_sound,
                                                                       self.__sound_command, self.__timeout)

        # fork in background
        if not self.__foreground:
            if os.fork() != 0:
                sys.exit(0)

        # debug
        if self.__debug:
            print("\n**********************")
            print("* !!! Debug Mode !!! *")
            print("**********************\n")
            self.__print_debug_info()
            # print("\n**********************")
            # print("* !!! Debug Mode !!! *")
            # print("**********************\n")

    def __print_debug_info(self):
        print("- Battmon version: %s" % VERSION)
        print("- python version: %s.%s.%s\n" % (sys.version_info[0], sys.version_info[1], sys.version_info[2]))
        print("- debug: %s" % self.__debug)
        print("- dry run: %s" % self.__test)
        print("- foreground: %s" % self.__foreground)
        print("- run more instances: %s" % self.__more_then_one_instance)
        print("- screen lock command: '%s'" % self.__screenlock_command)
        print("- use notifications: %s" % self.__disable_notifications)
        print("- show only critical notifications: %s" % self.__show_only_critical)
        print("- play sounds: %s" % self.__play_sound)
        print("- sound file path: '%s'" % self.__sound_file)
        print("- sound volume level: %s" % self.__sound_volume)
        print("- sound command: '%s'" % self.__sound_command)
        print("- notification timeout: %ssec" % int(self.__timeout / 1000))
        print("- battery update timeout: %ssec" % self.__battery_update_timeout)
        print("- battery low level value: %s%%" % self.__battery_low_value)
        print("- battery critical level value: %s%%" % self.__battery_critical_value)
        print("- battery hibernate level value: %s%%" % self.__battery_minimal_value)
        print("- battery minimal level value command: '%s'" % self.__minimal_battery_level_command)
        print("- no battery remainder: %smin" % self.__set_no_battery_remainder)
        print("- disable startup notifications: %s\n" % self.__disable_startup_notifications)

    # set name for this program, thus works 'killall Battmon'
    def __set_proc_name(self, name):
        # dirty hack to set 'Battmon' process name under python3
        libc = cdll.LoadLibrary('libc.so.6')
        if sys.version_info[0] == 3:
            libc.prctl(15, c_char_p(b'Battmon'), 0, 0, 0)
        else:
            libc.prctl(15, name, 0, 0, 0)

    # check if given program is running
    def __check_if_running(self, name):
        output = str(subprocess.check_output(['ps', '-A']))
        # check if process is running
        if name in output:
            return True
        else:
            return False

    # check if in path
    def __check_in_path(self, program_name, path=EXTRA_PROGRAMS_PATH):
        try:
            for p in path:
                if os.path.isfile(p + program_name):
                    self.__current_program_path = (p + program_name)
                    return True
            else:
                return False
        except OSError as ose:
            print("Error: " + str(ose))

    # check if Battmon is already running
    def __check_if_battmon_already_running(self):
        if self.__check_if_running(PROGRAM_NAME):
            if self.__play_sound:
                os.popen(self.__sound_command)
            if self.__found_notify_send_command:
                notify_send_string = '''notify-send "BATTMON IS ALREADY RUNNING" %s %s''' \
                                     % ('-t ' + str(self.__timeout), '-a ' + PROGRAM_NAME)
                os.popen(notify_send_string)
                sys.exit(1)
            else:
                print("BATTMON IS ALREADY RUNNING")
                sys.exit(1)

    # check for notify-send command
    def __check_notify_send(self):
        if self.__check_in_path('notify-send'):
            self.__found_notify_send_command = True
        else:
            self.__found_notify_send_command = False
            print("DEPENDENCY MISSING:\nYou have to install libnotify to have notifications.")

    # check if we have sound player
    def __check_play(self):
        if self.__check_in_path(DEFAULT_PLAYER_COMMAND):
            self.__sound_player = self.__current_program_path
            return True
        # if not found sox in path, send notification about it
        elif self.__found_notify_send_command:
            self.__play_sound = False
            notify_send_string = '''notify-send "DEPENDENCY MISSING\n" \
                                "You have to install sox to play sounds" %s %s''' \
                                 % ('-t ' + str(30 * 1000), '-a ' + PROGRAM_NAME)
            os.popen(notify_send_string)
        elif not self.__found_notify_send_command:
            self.__play_sound = False
            print("DEPENDENCY MISSING:\n You have to install sox to play sounds.\n")
        else:
            return False

    # check if sound files exist
    def __set_sound_file_and_volume(self):
        if os.path.exists(self.__sound_file):
            self.__sound_command = '%s -V1 -q -v%s %s' % (self.__sound_player, self.__sound_volume, self.__sound_file)
        else:
            if self.__found_notify_send_command:
                # missing dependency notification will disappear after 30 seconds
                message_string = ("Check if you have sound files exist:  \n %s\n"
                                  " If you've specified your own sound file path, "
                                  " please check if it was correctly") % self.__sound_file
                notify_send_string = '''notify-send "DEPENDENCY MISSING\n" "%s" %s %s''' \
                                     % (message_string, '-t ' + str(30 * 1000), '-a ' + PROGRAM_NAME)
                os.popen(notify_send_string)
            if not self.__found_notify_send_command:
                print("DEPENDENCY MISSING:\n Check if you have sound files in %s. \n"
                      "If you've specified your own sound file path, please check if it was correctly %s %s"
                      % self.__sound_file)
            self.__sound_command = "Not found"

    # check for lock screen program
    def __set_lock_command(self):
        if self.__screenlock_command == '':
            for c in SCREEN_LOCK_COMMANDS:
                # check if the given command was found in given path
                lock_command_as_list = c.split()
                command = lock_command_as_list[0]
                command_args = ' '.join(lock_command_as_list[1:len(lock_command_as_list)])
                if self.__check_in_path(command):
                    self.__screenlock_command = command + ' ' + command_args
                    if self.__found_notify_send_command and not self.__disable_startup_notifications:
                        notify_send_string = '''notify-send "Using '%s' to lock screen\n" "with args: %s" %s %s''' \
                                             % (
                                             command, command_args, '-t ' + str(self.__timeout), '-a ' + PROGRAM_NAME)
                        os.popen(notify_send_string)
                    elif not self.__disable_startup_notifications:
                        print("%s %s will be used to lock screen" % (command, command_args))
                    elif not self.__disable_startup_notifications and not self.__found_notify_send_command:
                        print("using default program to lock screen")
            if self.__screenlock_command == '':
                if self.__found_notify_send_command:
                    # missing dependency notification will disappear after 30 seconds
                    message_string = ("Check if you have installed any screenlock program,\n"
                                      " you can specify your favorite screenlock\n"
                                      " program running battmon with -lp '[PATH] [ARGS]',\n"
                                      " otherwise your session won't be locked")
                    notify_send_string = '''notify-send "DEPENDENCY MISSING\n" "%s" %s %s''' \
                                         % (message_string, '-t ' + str(30 * 1000), '-a ' + PROGRAM_NAME)
                    os.popen(notify_send_string)
                if not self.__found_notify_send_command:
                    print("DEPENDENCY MISSING:\n please check if you have installed any screenlock program, \
                            you can specify your favorite screen lock program \
                            running this program with -l PATH, \
                            otherwise your session won't be locked")
        elif not self.__screenlock_command == '':
            lock_command_as_list = self.__screenlock_command.split()
            command = lock_command_as_list[0]
            command_args = ' '.join(lock_command_as_list[1:len(lock_command_as_list)])
            if self.__found_notify_send_command and not self.__disable_startup_notifications:
                notify_send_string = '''notify-send "Using '%s' to lock screen\n" "with args: %s" %s %s''' \
                                     % (command, command_args, '-t ' + str(self.__timeout), '-a ' + PROGRAM_NAME)
                os.popen(notify_send_string)
            elif not self.__disable_startup_notifications:
                print("%s %s will be used to lock screen" % (command, command_args))
            elif not self.__disable_startup_notifications and not self.__found_notify_send_command:
                print("using default program to lock screen")

    # set critical battery value command
    def __set_minimal_battery_level_command(self):
        minimal_battery_commands = ['shutdown', 'pm-hibernate', 'pm-suspend', 'pm-suspend-hybrid', 'suspend.sh', 'hibernate.sh']

        power_off_command = ''
        hibernate_command = ''
        suspend_hybrid_command = ''
        suspend_command = ''

        # since upower dropped dbus-send methods we don't use this
        # if self.__check_if_running('upower'):
        #    power_off_command = "dbus-send --system --print-reply --dest=org.freedesktop.ConsoleKit " \
        #                        "/org/freedesktop/ConsoleKit/Manager org.freedesktop.ConsoleKit.Manager.Stop"
        #    hibernate_command = "dbus-send --system --print-reply --dest=org.freedesktop.UPower " \
        #                        "/org/freedesktop/UPower org.freedesktop.UPower.Hibernate"
        #    suspend_command = "dbus-send --system --print-reply --dest=org.freedesktop.UPower " \
        #                      "/org/freedesktop/UPower org.freedesktop.UPower.Suspend"

        for c in minimal_battery_commands:
            if self.__check_in_path(c):
                print("COMMAND:  %s" % c)
                if c == 'pm-hibernate' and self.__minimal_battery_level_command == "hibernate":
                    hibernate_command = "sudo %s" % c
                    break
                elif c == 'pm-suspend-hybrid' and self.__minimal_battery_level_command == "hybrid":
                    suspend_hybrid_command = "sudo %s" % c
                    break
                elif c == 'pm-suspend' and self.__minimal_battery_level_command == "suspend":
                    suspend_command = "sudo %s" % c
                    break
                else:
                    if c == 'hibernate.sh' and self.__minimal_battery_level_command == "hibernate":
                        hibernate_command = "sudo %s/bin/%s" % (PROGRAM_PATH, c)
                        break
                    elif c == 'suspend.sh' and self.__minimal_battery_level_command == "suspend":
                        suspend_command = "sudo %s/bin/%s" % (PROGRAM_PATH, c)
                        break
                    elif c == 'shutdown' and self.__minimal_battery_level_command == "shutdown":
                        power_off_command = "sudo %s/bin/shutdown.sh" % PROGRAM_PATH
                        break
            else:
                power_off_command = "sudo %s/bin/shutdown.sh" % PROGRAM_PATH

        if hibernate_command:
            self.__minimal_battery_level_command = hibernate_command
            self.__short_minimal_battery_command = "HIBERNATE"
        elif suspend_command:
            self.__minimal_battery_level_command = suspend_command
            self.__short_minimal_battery_command = "SUSPEND"
        elif suspend_hybrid_command:
            self.__minimal_battery_level_command = suspend_hybrid_command
            self.__short_minimal_battery_command = "SUSPEND BOTH"
        elif power_off_command:
            self.__minimal_battery_level_command = power_off_command
            self.__short_minimal_battery_command = "SHUTDOWN"

        if not (hibernate_command or suspend_command or power_off_command or suspend_hybrid_command):
            if self.__found_notify_send_command:
                # missing dependency notification will disappear after 30 seconds
                message_string = ("please check if you have installed pm-utils, or *KIT upower...\n"
                                  "or be sure that you can execute hibernate.sh and suspend.sh files in bin folder, \n"
                                  "otherwise your system will be SHUTDOWN on critical battery level")
                notify_send_string = '''notify-send "MINIMAL BATTERY VALUE PROGRAM NOT FOUND\n" "%s" %s %s''' \
                                     % (message_string, '-t ' + str(30 * 1000), '-a ' + PROGRAM_NAME)
                os.popen(notify_send_string)
            elif not self.__found_notify_send_command:
                print('''MINIMAL BATTERY VALUE PROGRAM NOT FOUND\n
                      please check if you have installed pm-utils,\n 
                      or *KIT upower... otherwise your system will be SHUTDOWN at critical battery level''')

        if self.__found_notify_send_command and not self.__disable_startup_notifications:
            notify_send_string = '''notify-send "System will be: %s\n" "below minimal battery level" %s %s''' \
                                 % (self.__short_minimal_battery_command, '-t ' + str(self.__timeout),
                                    '-a ' + PROGRAM_NAME)
            os.popen(notify_send_string)
        elif not self.__disable_startup_notifications and not self.__found_notify_send_command:
            print("below minimal battery level system will be: %s" % self.__short_minimal_battery_command)

    # check for battery update times
    def __check_battery_update_times(self):
        while self.__battery_values.battery_time() == 'Unknown':
            if self.__debug:
                print("DEBUG: battery value is %s, next check in %d sec"
                      % (str(self.__battery_values.battery_time()), self.__battery_update_timeout))
            time.sleep(self.__battery_update_timeout)
            if self.__battery_values.battery_time() == 'Unknown':
                if self.__debug:
                    print("DEBUG: battery value is still %s, continuing anyway"
                          % str(self.__battery_values.battery_time()))
                break

    # start main loop
    def run_main_loop(self):
        while True:
            # check if we have battery
            while self.__battery_values.is_battery_present():
                # check if battery is discharging to stay in normal battery level
                if not self.__battery_values.is_ac_present() and self.__battery_values.is_battery_discharging():
                    # discharging and battery level is greater then battery_low_value
                    if (self.__battery_values.battery_current_capacity() > self.__battery_low_value
                        and not self.__battery_values.is_ac_present()):
                        if self.__debug:
                            print("DEBUG: Discharging check (%s() in MainRun class)"
                                  % self.run_main_loop.__name__)
                        # notification
                        self.__check_battery_update_times()
                        self.notification.battery_discharging(self.__battery_values.battery_current_capacity(),
                                                              self.__battery_values.battery_time())
                        # have enough power and check if we should stay in save battery level loop
                        while (self.__battery_values.battery_current_capacity() > self.__battery_low_value
                               and not self.__battery_values.is_ac_present()):
                            time.sleep(1)

                    # low capacity level
                    elif (self.__battery_low_value >= self.__battery_values.battery_current_capacity() >
                              self.__battery_critical_value and not self.__battery_values.is_ac_present()):
                        if self.__debug:
                            print("DEBUG: Low level battery check (%s() in MainRun class)"
                                  % self.run_main_loop.__name__)
                        # notification
                        self.__check_battery_update_times()
                        self.notification.low_capacity_level(self.__battery_values.battery_current_capacity(),
                                                             self.__battery_values.battery_time())
                        # battery have enough power and check if we should stay in low battery level loop
                        while self.__battery_low_value >= self.__battery_values.battery_current_capacity() > \
                                self.__battery_critical_value and not self.__battery_values.is_ac_present():
                            time.sleep(1)

                    # critical capacity level
                    elif self.__battery_critical_value >= self.__battery_values.battery_current_capacity() > \
                            self.__battery_minimal_value and not self.__battery_values.is_ac_present():
                        if self.__debug:
                            print("DEBUG: Critical battery level check (%s() in MainRun class)"
                                  % self.run_main_loop.__name__)
                        # notification
                        self.__check_battery_update_times()
                        self.notification.critical_battery_level(self.__battery_values.battery_current_capacity(),
                                                                 self.__battery_values.battery_time())
                        # battery have enough power and check if we should stay in critical battery level loop
                        while self.__battery_critical_value >= self.__battery_values.battery_current_capacity() > \
                                self.__battery_minimal_value and not self.__battery_values.is_ac_present():
                            time.sleep(1)

                    # hibernate level
                    elif (self.__battery_values.battery_current_capacity() <= self.__battery_minimal_value
                          and not self.__battery_values.is_ac_present()):
                        if self.__debug:
                            print("DEBUG: Hibernate battery level check (%s() in MainRun class)"
                                  % self.run_main_loop.__name__)
                        # notification
                        self.__check_battery_update_times()
                        self.notification.minimal_battery_level(self.__battery_values.battery_current_capacity(),
                                                                self.__battery_values.battery_time(),
                                                                self.__short_minimal_battery_command,
                                                                (10 * 1000))
                        # check once more if system should be hibernate
                        if self.__battery_values.battery_current_capacity() <= self.__battery_minimal_value \
                                and not self.__battery_values.is_ac_present():
                            # the real thing
                            if not self.__test:
                                if self.__battery_values.battery_current_capacity() <= self.__battery_minimal_value \
                                        and not self.__battery_values.is_ac_present():
                                    # first warning, beep 5 times every two seconds, and display popup
                                    for i in range(5):
                                        # check if ac was plugged
                                        if (self.__battery_values.battery_current_capacity()
                                                <= self.__battery_minimal_value
                                            and not self.__battery_values.is_ac_present()):
                                            time.sleep(2)
                                            os.popen(self.__sound_command)
                                        # ac plugged, then bye
                                        else:
                                            break
                                    # one more check if ac was plugged
                                    if (self.__battery_values.battery_current_capacity()
                                            <= self.__battery_minimal_value
                                        and not self.__battery_values.is_ac_present()):
                                        time.sleep(2)
                                        os.popen(self.__sound_command)
                                        message_string = ("last chance to plug in AC cable...\n"
                                                          " system will be %s in 10 seconds\n"
                                                          " current capacity: %s%s\n"
                                                          " time left: %s") % (self.__short_minimal_battery_command,
                                                                               self.__battery_values.battery_current_capacity(),
                                                                               '%',
                                                                               self.__battery_values.battery_time())

                                        notify_send_string = '''notify-send "!!! MINIMAL BATTERY LEVEL !!!\n" \
                                                                "%s" %s %s''' \
                                                             % (message_string, '-t ' + str(10 * 1000),
                                                                '-a ' + PROGRAM_NAME)
                                        os.popen(notify_send_string)
                                        time.sleep(10)
                                    # LAST CHECK before hibernating
                                    if (self.__battery_values.battery_current_capacity()
                                            <= self.__battery_minimal_value
                                        and not self.__battery_values.is_ac_present()):
                                        # lock screen and hibernate
                                        for i in range(4):
                                            time.sleep(5)
                                            os.popen(self.__sound_command)
                                        time.sleep(1)
                                        os.popen(self.__screenlock_command)
                                        os.popen(self.__minimal_battery_level_command)
                                    else:
                                        break
                            # test block
                            elif self.__test:
                                for i in range(5):
                                    if self.__play_sound:
                                        os.popen(self.__sound_command)
                                    if (self.__battery_values.battery_current_capacity() <= self.__battery_minimal_value
                                        and not self.__battery_values.is_ac_present()):
                                        time.sleep(2)
                                print("TEST: Hibernating... Program goes sleep for 10sek")
                                time.sleep(10)
                        else:
                            pass

                # check if we have ac connected
                if self.__battery_values.is_ac_present() and not self.__battery_values.is_battery_discharging():
                    # full charged
                    if (self.__battery_values.is_ac_present()
                        and self.__battery_values.is_battery_fully_charged()
                        and not self.__battery_values.is_battery_discharging()):
                        if self.__debug:
                            print("DEBUG: Full battery check (%s() in MainRun class)"
                                  % self.run_main_loop.__name__)
                        # notification
                        # simulate self.__check_battery_update_times() behavior
                        time.sleep(self.__battery_update_timeout)
                        self.notification.full_battery()
                        # battery fully charged loop
                        while (self.__battery_values.is_ac_present()
                               and self.__battery_values.is_battery_fully_charged()
                               and not self.__battery_values.is_battery_discharging()):
                            if not self.__battery_values.is_battery_present():
                                self.notification.battery_removed()
                                if self.__debug:
                                    print("DEBUG: Battery removed !!! (%s() in MainRun class)"
                                          % self.run_main_loop.__name__)
                                time.sleep(self.__timeout / 1000)
                                break
                            else:
                                time.sleep(1)

                    # ac plugged and battery is charging
                    if (self.__battery_values.is_ac_present()
                        and not self.__battery_values.is_battery_fully_charged()
                        and not self.__battery_values.is_battery_discharging()):
                        if self.__debug:
                            print("DEBUG: Charging check (%s() in MainRun class)"
                                  % self.run_main_loop.__name__)
                        # notification
                        self.__check_battery_update_times()
                        self.notification.battery_charging(self.__battery_values.battery_current_capacity(),
                                                           self.__battery_values.battery_time())

                        # battery charging loop
                        while (self.__battery_values.is_ac_present()
                               and not self.__battery_values.is_battery_fully_charged()
                               and not self.__battery_values.is_battery_discharging()):
                            if not self.__battery_values.is_battery_present():
                                self.notification.battery_removed()
                                if self.__debug:
                                    print("DEBUG: Battery removed (%s() in MainRun class)"
                                          % self.run_main_loop.__name__)
                                time.sleep(self.__timeout / 1000)
                                break
                            else:
                                time.sleep(1)

            # check for no battery
            if not self.__battery_values.is_battery_present() and self.__battery_values.is_ac_present():
                # notification
                self.notification.no_battery()
                if self.__debug:
                    print("DEBUG: No battery check (%s() in MainRun class)"
                          % self.run_main_loop.__name__)
                # no battery remainder loop counter
                no_battery_counter = 1
                # loop to deal with situation when we don't have battery
                while not self.__battery_values.is_battery_present():
                    if self.__set_no_battery_remainder > 0:
                        remainder_time_in_sek = self.__set_no_battery_remainder * 60
                        time.sleep(1)
                        no_battery_counter += 1
                        # check if battery was plugged
                        if self.__battery_values.is_battery_present():
                            self.notification.battery_plugged()
                            if self.__debug:
                                print("DEBUG: Battery plugged (%s() in MainRun class)"
                                      % self.run_main_loop.__name__)
                            time.sleep(self.__timeout / 1000)
                            break
                        # send no battery notifications and reset no_battery_counter
                        if not self.__battery_values.is_battery_present() \
                                and no_battery_counter == remainder_time_in_sek:
                            self.notification.no_battery()
                            no_battery_counter = 1
                    else:
                        # no action wait
                        time.sleep(1)
                        # check if battery was plugged
                        if self.__battery_values.is_battery_present():
                            self.notification.battery_plugged()
                            if self.__debug:
                                print("DEBUG: Battery plugged (%s() in MainRun class)"
                                      % self.run_main_loop.__name__)
                            time.sleep(self.__timeout / 1000)
                            break


if __name__ == '__main__':
    # main parser
    ap = argparse.ArgumentParser(usage="Usage: %(prog)s [OPTION...]", description=DESCRIPTION,
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                 epilog=EPILOG)

    # group parsers
    file_group = ap.add_argument_group("File path arguments")
    battery_group = ap.add_argument_group("Battery arguments")
    sound_group = ap.add_argument_group("Sound arguments")
    notification_group = ap.add_argument_group("Notification arguments")

    # default options
    defaultOptions = {"debug": False,
                      "test": False,
                      "foreground": False,
                      "more_then_one_instance": False,
                      "lock_command": DEFAULT_SCREEN_LOCK_COMMAND,
                      "disable_notifications": False,
                      "critical": False,
                      "sound_file": DEFAULT_SOUND_FILE_PATH,
                      "play_sound": True,
                      "sound_volume": 3,
                      "timeout": 6,
                      "battery_update_timeout": 6,
                      "battery_low_value": 23,
                      "battery_critical_value": 14,
                      "battery_minimal_value": 7,
                      "minimal_battery_level_command": 'hybrid',
                      "set_no_battery_remainder": 0,
                      "disable_startup_notifications": False}

    ap.add_argument("-v", "--version",
                    action="version",
                    version=VERSION)

    # debug options
    ap.add_argument("-d", "--debug",
                    action="store_true",
                    dest="debug",
                    default=defaultOptions['debug'],
                    help="print debug information, implies -f, option")

    # dry run
    ap.add_argument("-dr", "--dry-run",
                    action="store_true",
                    dest="test",
                    default=defaultOptions['test'],
                    help="dry run")

    # daemon
    ap.add_argument("-f", "--foreground",
                    action="store_true",
                    dest="foreground",
                    default=defaultOptions['foreground'],
                    help="run in foreground]")

    # allows to run only one instance of this program
    ap.add_argument("-i", "--run-more-instances",
                    action="store_true",
                    dest="more_then_one_instance",
                    default=defaultOptions['more_then_one_instance'],
                    help="run more then one instance")

    # lock command setter
    file_group.add_argument("-lp", "--lock-command-path",
                            action="store",
                            dest="lock_command",
                            type=str,
                            # nargs="*",
                            metavar='''"<PATH> <ARGS>"''',
                            default=defaultOptions['lock_command'],
                            help="path to screenlock command with arguments if any, need to be surrounded with quotes")

    # show notifications
    notification_group.add_argument("-n", "--disable-notifications",
                                    action="store_true",
                                    dest="disable_notifications",
                                    default=defaultOptions['disable_notifications'],
                                    help="disable notifications")

    # show only critical notifications
    notification_group.add_argument("-cn", "--critical-notifications",
                                    action="store_true",
                                    dest="critical",
                                    default=defaultOptions['critical'],
                                    help="show only critical battery notifications")

    # set sound file path
    file_group.add_argument("-sp", "--sound-file-path",
                            action="store",
                            dest="sound_file",
                            type=str,
                            metavar="<PATH>",
                            default=defaultOptions['sound_file'],
                            help="path to sound file")

    # don't play sound
    sound_group.add_argument("-ns", "--no-sound",
                             action="store_false",
                             dest="play_sound",
                             default=defaultOptions['play_sound'],
                             help="disable sounds")


    # set sound volume level
    def set_sound_volume_level(volume_value):
        volume_value = int(volume_value)
        if volume_value < 1:
            raise argparse.ArgumentError(volume_value, "Sound level must be greater then 1")
        if volume_value > MAX_SOUND_VOLUME_LEVEL:
            raise argparse.ArgumentError(volume_value, "Sound level can't be greater then %s" % MAX_SOUND_VOLUME_LEVEL)
        return volume_value


    # sound level volume
    sound_group.add_argument("-sl", "--set-sound-loudness",
                             dest="sound_volume",
                             type=set_sound_volume_level,
                             metavar="<1-%d>" % MAX_SOUND_VOLUME_LEVEL,
                             default=defaultOptions['sound_volume'],
                             help="sound volume level")


    # check if notify timeout is correct >= 0
    def set_timeout(timeout):
        timeout = int(timeout)
        if timeout < 0:
            raise argparse.ArgumentError(timeout, "Notification timeout should be 0 or positive number")
        return timeout


    # timeout
    notification_group.add_argument("-t", "--timeout",
                                    dest="timeout",
                                    type=set_timeout,
                                    metavar="<SECONDS>",
                                    default=defaultOptions['timeout'],
                                    help="notification timeout (use 0 to disable)")


    # check if battery update interval is correct >= 0
    def set_battery_update_interval(update_value):
        update_value = int(update_value)
        if update_value <= 0:
            raise argparse.ArgumentError(update_value, "Battery update interval should be positive number")
        return update_value


    # battery update interval
    battery_group.add_argument("-bu", "--battery-update-interval",
                               dest="battery_update_timeout",
                               type=set_battery_update_interval,
                               metavar="<SECONDS>",
                               default=defaultOptions['battery_update_timeout'],
                               help="battery values update interval")

    # battery low level value
    battery_group.add_argument("-ll", "--low-level-value",
                               dest="battery_low_value",
                               type=int,
                               metavar="<1-100>",
                               default=defaultOptions['battery_low_value'],
                               help="battery low value")

    # battery critical value
    battery_group.add_argument("-cl", "--critical-level-value",
                               dest="battery_critical_value",
                               type=int,
                               metavar="<1-100>",
                               default=defaultOptions['battery_critical_value'],
                               help="battery critical value")

    # battery minimal value
    battery_group.add_argument("-ml", "--minimal-level-value",
                               dest="battery_minimal_value",
                               type=int,
                               metavar="<1-100>",
                               default=defaultOptions['battery_minimal_value'],
                               help="battery minimal value")

    # set minimal battery level command
    battery_group.add_argument("-mc", "--minimal-level-command",
                               action="store",
                               dest="minimal_battery_level_command",
                               type=str,
                               metavar="<ARG>",
                               choices=['hibernate', 'suspend', 'poweroff', 'hybrid'],
                               default=defaultOptions['minimal_battery_level_command'],
                               help='''set minimal battery value action, possible actions are: \
                                    'hibernate', 'suspend', 'hybrid' and 'poweroff' ''')


    # set no battery notification
    def set_no_battery_remainder(remainder):
        remainder = int(remainder)
        if remainder < 0:
            raise argparse.ArgumentError(remainder, "'no battery' remainder value must be greater or equal 0")
        return remainder


    # set 'no battery' notification timeout, default 0
    notification_group.add_argument("-br", "--set_no_battery_remainder",
                                    dest="set_no_battery_remainder",
                                    type=set_no_battery_remainder,
                                    metavar="<MINUTES>",
                                    default=defaultOptions['set_no_battery_remainder'],
                                    help="set 'no battery' remainder in minutes, 0 disables")

    # don't show startup notifications
    notification_group.add_argument("-dn", "--disable-startup-notifications",
                                    action="store_true",
                                    dest="disable_startup_notifications",
                                    default=defaultOptions['disable_startup_notifications'],
                                    help="don't show startup notifications, like screenlock \
                                          command or minimal battery level action")

    # parse help
    args = ap.parse_args()


    # battery low value setter
    def check_battery_low_value(low_value):
        low_value = int(low_value)
        if low_value > 100 or low_value <= 0:
            ap.error("\nLow battery level must be a positive number between 1 and 100")
        if low_value <= args.battery_critical_value:
            ap.error("\nLow battery level %s must be greater than %s (critical battery value)"
                     % (args.battery_low_value, args.battery_critical_value))
        if low_value <= args.battery_minimal_value:
            ap.error("\nLow battery level must %s be greater than %s (minimal battery value)"
                     % (args.battery_low_value, args.battery_minimal_value))


    # battery critical value setter
    def check_battery_critical_value(critical_value):
        critical_value = int(critical_value)
        if critical_value > 100 or critical_value <= 0:
            ap.error("\nCritical battery level must be a positive number between 1 and 100")
        if critical_value >= args.battery_low_value:
            ap.error("\nCritical battery level %s must be smaller than %s (low battery value)"
                     % (args.battery_critical_value, args.battery_low_value))
        if critical_value <= args.battery_minimal_value:
            ap.error("\nCritical battery level %s must be greater than %s (minimal battery value)"
                     % (args.battery_low_value, args.battery_minimal_value))


    # battery minimal value setter
    def check_battery_minimal_value(minimal_value):
        minimal_value = int(minimal_value)
        if minimal_value > 100 or minimal_value <= 0:
            ap.error("\nMinimal battery level must be a positive number between 1 and 100")
        if minimal_value >= args.battery_low_value:
            ap.error("\nEMinimal battery level %s must be smaller than %s (low battery value)"
                     % (args.battery_minimal_value, args.battery_low_value))
        if minimal_value >= args.battery_critical_value:
            ap.error("\nMinimal battery level %s must be smaller than %s (critical battery value)"
                     % (args.battery_minimal_value, args.battery_critical_value))


    # check battery arguments
    check_battery_low_value(args.battery_low_value)
    check_battery_critical_value(args.battery_critical_value)
    check_battery_minimal_value(args.battery_minimal_value)

    # let's go
    ml = MainRun(**vars(args))
    ml.run_main_loop()
