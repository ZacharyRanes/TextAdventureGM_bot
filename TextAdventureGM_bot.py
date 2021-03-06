#Author: Zachary Ranes

import copy
import os
from configparser import ConfigParser

import requests
from telebot import TeleBot, types

from agf_parser import agf_parser as parser

#This loads a config file that holds the bots API key
config = ConfigParser()
config.read("TextAdventureGM_config.cfg")
TOKEN = config.get("telegram_bot_api","telegram_token")
bot = TeleBot(TOKEN)

#Loads adventure game files from long term storage on bot startup
def load_files():
    try:
        dic = {}
        for filename in os.listdir('adventures/'):
            filepath = 'adventures/'+filename
            dic[filename] = parser.loadAGF(filepath)
        return dic
    except:
        os.makedirs('adventures/', exist_ok=True)
        return {}

#key is a chat id holds an message id (message waiting to be replied to)
waiting = {}
#key is original file names holds adventure game objects
adventures = load_files()
#key is chat id hold edited adventure game objects
running_adventures = {}

#Help command will display the instruction file to the chat 
@bot.message_handler(commands=['help'])
def command_help(message):
    with open("TextAdventure_instructions.txt", "rb") as instructions:
        bot.reply_to(message, instructions.read()) 

#Gives the option to start playing a game or upload one
@bot.message_handler(commands=['start'])
def command_start(message):
    bot.reply_to(message, "To /start_adventure use this command\n"\
                          "To /upload_adventure use this command\n"\
                          "For /help with agf formatting use this command")

#Prompts for a reply of an adventure file and preps for upload_reply_handler
@bot.message_handler(commands=['upload_adventure'])
def command_upload_adventure(message):
    reply = bot.reply_to(message, "Please reply to this message with an adventure file")
    key = message.chat.id
    waiting[key] = reply.message_id

#Reads in files from user responce 
@bot.message_handler(content_types=['document'])
def upload_reply_handler(message):
    key = message.chat.id
    if key in waiting and message.reply_to_message:
        if message.reply_to_message.message_id == waiting[key]:
            waiting.pop(key, None)
            bot.reply_to(message, "Reading/Parsing File...")
            try:
                file_info = bot.get_file(message.document.file_id)
                adventure_file = bot.download_file(file_info.file_path)
                name = message.document.file_name
                name = name.lower() #when files are saved to long term mem they are saved as lower this prevents when they load to make duplicates in select adventure menu
                adventures[name] = parser.parseAGF(adventure_file)
                parser.saveAGF(adventures[name], 'adventures/'+ name)
                bot.reply_to(message, "Done!")
            except Exception as ex:
                print(ex)
                bot.reply_to(message, "Parsing Failed, please read /help for intustions on formating adventure files")

#Shows options of uploaded adventured  
@bot.message_handler(commands=['start_adventure'])
def command_new_adventure(message):
    markup = types.InlineKeyboardMarkup()
    for a in adventures:
        title = adventures[a].adventureTitle()
        markup.row(types.InlineKeyboardButton(callback_data=a,
                                              text=title))
    bot.reply_to(message, "Which adventure do you want to play?", 
                                              reply_markup=markup)

#Handles the callback data sent from the new_adventure command 
@bot.callback_query_handler(func=lambda call:
                call.message.chat.id not in running_adventures and
                call.data in adventures)
def callback_start_new_adventure(call):
    key = call.message.chat.id
    title = adventures[call.data].adventureTitle()
    bot.edit_message_text("Which adventure do you want to play?\n"\
                          "==> " + title, 
                            message_id=call.message.message_id, 
                            chat_id=key, 
                            reply_markup=None)
    running_adventures[key] = copy.deepcopy(adventures[call.data])
    run_adventure(key)

#Called with the key to the running_adventures dic to show current choices
def run_adventure(key):
    text = running_adventures[key].state()
    choices = running_adventures[key].getChoices()
    markup = types.InlineKeyboardMarkup()
    index = 0
    for c in choices:
        #Text Adventure GM Choice
        data = "TAGMC" + str(index)
        markup.row(types.InlineKeyboardButton(callback_data=data, 
                                              text=c))
        index += 1
    bot.send_message(key, text, reply_markup=markup)

    if running_adventures[key].isEnd():
        if running_adventures[key].isWin():
            bot.send_message(key, "GM: Adventure completed")
            del running_adventures[key]
        else:
            bot.send_message(key, "GM: Adventure end...")
            del running_adventures[key]
    
#Handles the call back that clicking an inline choice sends
@bot.callback_query_handler(func=lambda call: 
                    call.message.chat.id in running_adventures and
                    call.data[:5] == "TAGMC")
def choice_handler(call):
    key = call.message.chat.id
    text = running_adventures[key].state()
    choices = running_adventures[key].getChoices()
    index = int(call.data[5:])
    #edit the original message to show the choices made and hide buttons
    bot.edit_message_text(text + "\n==> " + choices[index], 
                              message_id=call.message.message_id, 
                              chat_id=key, 
                              reply_markup=None)
    #Make choice then show next states
    running_adventures[key].choose(index)
    run_adventure(key)

#
@bot.message_handler(commands=['quit_adventure'])
def command_quit_adventure(message):
    if message.chat.id in running_adventures:
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton(callback_data="TAGMQY", text="Yes"),
            types.InlineKeyboardButton(callback_data="TAGMQN", text="No"))
        bot.reply_to(message, 
                    "Are you sure? All progress will be lost", 
                    reply_markup=markup)
    else:
        bot.reply_to(message, "There is not a running adventure in this chat")

#       
@bot.callback_query_handler(func=lambda call: 
                    call.message.chat.id in running_adventures and
                    call.data[:5] == "TAGMQ")
def quit_handler(call):
    key = call.message.chat.id
    if call.data[5:] == "Y":
        text = "Adventure Quit"
        del running_adventures[key]
    else:
        text = "Adventure Continues"
    bot.edit_message_text(text, 
                          message_id=call.message.message_id, 
                          chat_id=key, 
                          reply_markup=None)

if __name__ == '__main__':
    try:
        bot.polling(none_stop=True)
    except:
        print("Polling Crashed")