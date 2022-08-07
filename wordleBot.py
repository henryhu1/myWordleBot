import discord
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
mainChannel = None

bot = commands.Bot(command_prefix = 'Wrd')

WORDLE_LINK = discord.Embed()
WORDLE_LINK.description = "https://www.nytimes.com/games/wordle/index.html"

FIRST_WORDLE_DAY = datetime(2021, 6, 19)
START = datetime.today()
STARTING_WORDLE = START - FIRST_WORDLE_DAY
WORDLE_GAME_REACTIONS = ['\U0001F440', '\U0001F9E0', '\U0001F525', '\U0001F44D', '\U0001F921', '\U0001F4A9', '\U0001F44E']

wordlePlayerSet = set()
wordleResultList = [[], [], [], [], [], [], []]
playedAlreadySet = set()

class WordlePlayer:
    def __init__(self, discordId, name):
        self.discordId = discordId
        self.name = name
        # self.totalPlayed = 0
        # self.totalGuesses = 0
        # self.avgGuesses = 0
        self.wins = 0

    def __repr__(self):
        return self.name

def filterExistingPlayers(discordId):
    return list(filter(lambda player: (player.discordId == discordId) , wordlePlayerSet))

def createPlayer(discordId, name):
    newPlayer = WordlePlayer(discordId, name)
    wordlePlayerSet.add(newPlayer)
    return newPlayer

def getStanding(final):
    global wordleResultList
    finalResult = ''
    standing = 1
    for guess in range(len(wordleResultList)):
        for player in wordleResultList[guess]:
            if final and standing == 1: player.wins += 1
            finalResult += str(standing) + ': ' + player.name
            finalResult += ' - ' + str(guess + 1) + ' {0}'.format('guess' if guess == 0 else 'guesses') + '\n'
            standing += 1
    return 'No one played Wordle today...' if finalResult == '' else finalResult

async def finalResults():
    global wordleResultList
    global playedAlreadySet
    finalResult = getStanding(True)
    await mainChannel.send('Today\'s results!\n{0}\nNext Wordle is here!'.format(finalResult), embed = WORDLE_LINK)
    playedAlreadySet = set()
    wordleResultList = [[], [], [], [], [], [], []]

@bot.event
async def on_ready():
    print('We have logged in as {0.user}\n'.format(bot))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(finalResults, CronTrigger(hour=23, minute=59, second=59)) 
    scheduler.start()

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    await bot.process_commands(message)

    if message.content.startswith('Wordle'):
        wordleMessage = message.content.split()
        gameNumber = wordleMessage[1]
        result = wordleMessage[2].split('/')
        totalAttempts = result[1]
        guesses = wordleMessage[3:]
        currentWordle = (datetime.today() - FIRST_WORDLE_DAY).days
        if not gameNumber.isdigit() or int(gameNumber) != currentWordle:
            await message.channel.send('That Wordle game is not today\'s game!')
        elif len(result) != 2:
            raise discord.DiscordException
        elif totalAttempts != "6":
            await message.channel.send('There should be 6 attempts, not {0}!'.format(totalAttempts))
        else:
            correctOn = result[0]
            discordId = message.author.id
            if correctOn == "X" or correctOn.isdigit() and int(correctOn) <= 5 and int(correctOn) == len(guesses):
                if discordId in playedAlreadySet:
                    await message.channel.send('You already played today\'s Wordle!')
                else:
                    guessIndex = 6 if correctOn == "X" else int(correctOn) - 1
                    await message.add_reaction(WORDLE_GAME_REACTIONS[guessIndex])
                    existing = filterExistingPlayers(discordId)
                    if len(existing) == 0:
                        await message.channel.send('New Wordle player!?')
                        newPlayer = createPlayer(discordId, message.author.name)
                        wordleResultList[guessIndex].append(newPlayer)
                    else:
                        wordleResultList[guessIndex].append(existing[0])
                    playedAlreadySet.add(discordId)
            else:
                raise discord.DiscordException

    elif message.content.startswith('WrdHere'):
        await message.add_reaction('\U0001F447')

# @bot.event
# async def on_error(event, *args, **kwargs):
#     print(event, args, kwargs)
#     with open('err.log', 'a') as f:
#         if event == 'on_message':
#             f.write(f'Unhandled message: {args[0]}\n')
#         else:
#             raise

@bot.command(name = 'Here')
async def setChannel(ctx):
    global mainChannel
    mainChannel = ctx.channel

@bot.command(name = 'Me')
async def getPlayerInfo(ctx):
    player = filterExistingPlayers(ctx.message.author.id)
    if len(player) == 0:
        await ctx.send('You haven\'t played Wordle before...')
    else:
        await ctx.send('{0.name} has {0.wins} {1}'.format(player[0], 'win' if player[0].wins == 1 else 'wins'))

@bot.command(name = 'Today')
async def getCurrentStandings(ctx):
    currentWordle = (datetime.today() - FIRST_WORDLE_DAY).days
    await ctx.send('Standings for Wordle {0} so far!\n{1}'.format(currentWordle, getStanding(False)))

@bot.command(name = 'Rankings')
async def getRankings(ctx):
    ranking = sorted(wordlePlayerSet, key = lambda player: player.wins)
    result = ''
    standing = 1
    previousPlayerWins = -1
    for player in ranking:
        result += str(standing) + ': ' + player.name
        result += ' - ' + str(player.wins) + ' '
        result += '{0}'.format('win' if player.wins == 1 else 'wins')
        if (player.wins != previousPlayerWins):
            previousPlayerWins = player.wins
            standing += 1
    await ctx.send('Current Wordle rankings!\n{0}'.format('No one has ever played Wordle...' if result == '' else result))

@bot.command(name = 'Bot')
async def botInfo(ctx):
    daysAgo = (datetime.today() - START).days
    await ctx.send('Started keeping track on Wordle {0} ({1} {2} ago)'.format(STARTING_WORDLE.days, daysAgo, 'day' if daysAgo == 1 else 'days'))

@bot.command(name = 'Help')
async def help(ctx):
    await ctx.send('''```Send your Wordle results!
WrdHere - Channel this command is sent in will get Wordle results at the end of the day
WrdMe - Check your stats
WrdToday - Check today\'s standings
WrdRankings - Check all-time rankings
WrdBot - Bot details```
Play Wordle!
    ''', embed = WORDLE_LINK)

bot.run(DISCORD_TOKEN)
