import telebot
from telebot.types import ReplyKeyboardMarkup
import requests
import json

import datetime
from pony.orm import *

# ORM
db = Database()
class Statistic(db.Entity):
    city = Required(str)
    name = Required(str)
    value = Required(int)
    current_time = Required(str)

db.bind(provider='sqlite', filename='database.sqlite', create_db=True)
set_sql_debug(True)
db.generate_mapping(create_tables=True)

# bot
token = '5119258458:AAHK15RqAID7I-Dmt4YJeIQUdqeGyqeT6xQ'
bot = telebot.TeleBot(token)

# api to get the sensor data
api_url = 'https://api.waqi.info/feed/'
token_key = '345adbca2e6f2c915b7fc787ee238d8f4dc7e0fe'
params = {'token': token_key}

states = {}
cities = {}

buttons = ['temp°C', 'PM2,5 μg/m3', 'check for another city','history of monitoring', 'start monitoring']
MAIN_STATE = 'main'
NEXT_STATE = 'next_state'
INFO_STATE = 'more_info'
# threshold, used for notification
threshold_P25 = 120


@bot.message_handler(func=lambda message: True)
def dispatcher(message):
    user_id = message.from_user.id
    state = states.get(user_id, MAIN_STATE)
    if state == MAIN_STATE:
        start_handler(message)
    elif state == NEXT_STATE:
        city_handler(message)
    elif state == INFO_STATE:
        info_handler(message)

def get_sensor_data(city):
    api_url_city = api_url + city + '/?'
    sensor_data = requests.get(api_url_city, params=params)
    sensor_data_text = json.loads(sensor_data.text)
    sensor_data_city = sensor_data_text['data']
    return sensor_data_city


def start_handler(message):
    if message.text == '/start':
        bot.reply_to(message, """This is your environment-bot.
I will help you to know about the
environment condition, by providing
information about the temperature - temp°C and the Particulate matter - PM2,5 in most of the cities.
Type the name of your city below!""")
        states[message.from_user.id] = NEXT_STATE

def city_handler(message):
    cities[message.from_user.id] = message.text
    user_id = message.from_user.id
    city = cities.get(user_id, None)
    
    # get the sensor data using the api
    sensor_data_city = get_sensor_data (city)
    # check if the api provides information for requested city
    city_is_available = check_city(city, sensor_data_city, message)
    if city_is_available:
        markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        markup.add(*buttons)
        bot.send_message(message.from_user.id, 'press any button to get more information, if available', reply_markup=markup)
        states[message.from_user.id] = INFO_STATE
    else:
        states[message.from_user.id] = MAIN_STATE

def check_city(city, sensor_data_city, message):
    status = True
    if sensor_data_city == 'Unknown station':
        bot.reply_to(message, 'unfortunately, this city is not supported by the Api! Type /start to choose another city!')
        status = False
    return status    

def get_info(sensor_city, req_info):
    info = 'no'
    param_sensor = sensor_city['iaqi']
    if req_info == 'PM2,5 μg/m3':
        if 'pm25' in param_sensor:
            info = param_sensor['pm25']
        else:     
            info = 'no'
    elif req_info == 'temp°C':
        info = (param_sensor['t'])
    elif req_info == 'check for another city':    
        info = 'no_city'
    elif req_info == 'history of monitoring':
        info = 'statistic'
    elif req_info == 'start monitoring':
        info = 'start_monitor'
    return info


def info_handler(message):
    user_id = message.from_user.id
    req_info = message.text
    city = cities.get(user_id, None)

    # get the sensor data using the api
    sensor_data_city = get_sensor_data (city)
    info = get_info(sensor_data_city, req_info)
    if info == 'no':
        bot.reply_to(message, 'unfortunately, this information is not availabe!') 
    elif info == 'no_city':
        bot.reply_to(message, "type /start")
        states[message.from_user.id] = MAIN_STATE
    elif info == 'statistic':
        with db_session:
            log = select(s for s in Statistic)[:]
            answer = f'the last measured {log[-1].name} = {log[-1].value} in {log[-1].city} at {log[-1].current_time}'
            bot.reply_to(message, answer)               
    elif info == 'start_monitor':
  
        value_prev = 0
        status_handler(info, message, value_prev)

    else:
        bot.reply_to(message, int(round(info['v'])))
        city = str(city)
        name = str(req_info)
        value = int(round(info['v']))
        current_time = str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))

        with db_session:
            v = Statistic(city = city, name = name, value = value, current_time = current_time)
            commit()
            

def status_handler(info, message, value_prev):
    user_id = message.from_user.id
    city = cities.get(user_id, None)
    # get the sensor data using the api
    sensor_data_city = get_sensor_data (city)
    # we are interesed only in level or particles, which critical than the temperature
    req_info = 'PM2,5 μg/m3'
    info = get_info(sensor_data_city, req_info)

    city = str(city)
    name = str(req_info)
    value = int(round(info['v']))
    
    current_time = str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    if (value > threshold_P25) & (value != value_prev):
        answer = f'the threshold ={threshold_P25} is achieved! {name} = {value} in {city} at {current_time}'
        bot.reply_to(message, answer)
        
    with db_session:
        v = Statistic(city = city, name = name, value = value, current_time = current_time)
        commit()
        log = select(s for s in Statistic)[:]
        value_prev = log[-2].value

    
    status_handler(info, message,value_prev)
    

bot.polling()



