import discord
import heapq
import json
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from datetime import timedelta
from discord.ext import commands
from dotenv import load_dotenv
from pytz import timezone

tz = timezone('America/New_York')

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
mainChannel = None

bot = commands.Bot(command_prefix = 'Wrd')

WORDLE_LINK = discord.Embed()
WORDLE_LINK.description = "https://www.nytimes.com/games/wordle/index.html"

FIRST_WORDLE_DAY = tz.localize(datetime(2021, 6, 19, 0, 0, 0))
START = tz.localize(datetime(2022, 8, 7, 0, 0, 0))
print(datetime.now(tz))
print(FIRST_WORDLE_DAY)
STARTING_WORDLE = START - FIRST_WORDLE_DAY
WORDLE_GAME_REACTIONS = ['\U0001F440', '\U0001F9E0', '\U0001F525', '\U0001F44D', '\U0001F921', '\U0001F4A9', '\U0001F44E']

wordlePlayerSet = set()
wordleResultList = [[], [], [], [], [], [], []]
playedAlreadySet = set()

class WordlePlayer:
    def __init__(self, discordId, name, wins, guessPriorityOrder):
        self.discordId = discordId
        self.name = name
        # self.totalPlayed = 0
        # self.totalGuesses = 0
        # self.avgGuesses = 0
        self.wins = wins
        self.guessPriorityOrder = guessPriorityOrder

    def toJson(self):
        return json.dumps(self, default = lambda o: o.__dict__, sort_keys = True, indent = 4)

    def __repr__(self):
        return self.name

    def __lt__(self, other):
        return self.guessPriorityOrder < other.guessPriorityOrder

def singularPluralDecider(singular, plural, value):
    return singular if value == 1 else plural

def getTodaysWordle():
    print(datetime.now(tz))
    print(FIRST_WORDLE_DAY)
    return (datetime.now(tz) - FIRST_WORDLE_DAY).days

def filterExistingPlayers(discordId):
    return list(filter(lambda player: (player.discordId == discordId) , wordlePlayerSet))

def createPlayer(discordId, name, priority):
    newPlayer = WordlePlayer(discordId, name, 0, priority)
    wordlePlayerSet.add(newPlayer)
    with open('players.txt', 'a') as f:
        f.write(f'{newPlayer.toJson()}\n')
    return newPlayer

def getStanding(final):
    global wordleResultList
    finalResult = ''
    standing = 1
    if final:
        with open('players.txt', 'w') as f:
            for guess in range(len(wordleResultList)):
                for player in wordleResultList[guess]:
                    if standing == 1: player.wins += 1
                    f.write(f'{player.toJson()}\n')
                    finalResult += str(standing) + ': ' + player.name
                    finalResult += ' - ' + str(guess + 1) + ' {0}'.format('guess' if guess == 0 else 'guesses') + '\n'
                    standing += 1
    else:
        for guess in range(len(wordleResultList)):
            for player in wordleResultList[guess]:
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
    wordleResultList.clear()
    wordleResultList = [[], [], [], [], [], [], []]
    open('playersToday.txt', 'w').close()

@bot.event
async def on_ready():
    global wordleResultList
    print('on_ready - right now and today\'s Wordle number', datetime.now(tz), getTodaysWordle())
    f = open("players.txt", "r")
    playerJson = ''
    for line in f.readlines():
        playerJson += line
        if '}' in line:
            playerData = json.loads(playerJson)
            playerJson = ''
            newPlayer = WordlePlayer(playerData['discordId'], playerData['name'], playerData['wins'], -1)
            wordlePlayerSet.add(newPlayer)
    f.close()

    f = open("playersToday.txt", "r")
    existingResults = [[], [], [], [], [], [], []]
    for line in f.readlines():
        playedToday = json.loads(line)
        print(playedToday['discordId'], playedToday['guessIndex'], playedToday['priority'])
        player = filterExistingPlayers(playedToday['discordId'])
        if (len(player) != 0):
            player[0].guessPriorityOrder = playedToday['priority']
            existingResults[playedToday['guessIndex']].append(player[0])
            playedAlreadySet.add(playedToday['discordId'])
    f.close()

    for bucket in existingResults:
        heapq.heapify(bucket)
    wordleResultList = existingResults

    scheduler = AsyncIOScheduler()
    scheduler.add_job(finalResults, CronTrigger(hour=3, minute=59, second=59)) 
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
        currentWordle = getTodaysWordle()
        print('on_message - currentWordle', currentWordle)
        if not gameNumber.isdigit() or int(gameNumber) != currentWordle:
            await message.channel.send('That Wordle game is not today\'s game!')
        elif len(result) != 2:
            await message.channel.send('{0} is not a valid result!'.format(wordleMessage[2]))
        elif totalAttempts != "6":
            await message.channel.send('There should be 6 attempts, not {0}!'.format(totalAttempts))
        else:
            correctOn = result[0]
            discordId = message.author.id
            if correctOn == "X" or correctOn.isdigit() and 0 < int(correctOn) <= 6 and int(correctOn) == len(guesses):
                if discordId in playedAlreadySet:
                    await message.channel.send('You already played today\'s Wordle!')
                else:
                    guessIndex = 6 if correctOn == "X" else int(correctOn) - 1
                    guessResultList = wordleResultList[guessIndex]
                    await message.add_reaction(WORDLE_GAME_REACTIONS[guessIndex])
                    existing = filterExistingPlayers(discordId)
                    if len(existing) != 0:
                        existing[0].guessOrderPriority = len(guessResultList)
                        guessResultList.append(existing[0])
                    else:
                        await message.channel.send('New Wordle player!?')
                        newPlayer = createPlayer(discordId, message.author.name, len(guessResultList))
                        guessResultList.append(newPlayer)
                    with open('playersToday.txt', 'a') as f:
                        playerTodayDict = { "discordId": discordId, "guessIndex": guessIndex, "priority": len(guessResultList) }
                        json.dump(playerTodayDict, f)
                        f.write('\n')
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
        await ctx.send('{0.name} has {0.wins} {1}'.format(player[0], singularPluralDecider('win', 'wins', player[0].wins)))

@bot.command(name = 'Today')
async def getCurrentStandings(ctx):
    rightNow = datetime.now(tz)
    midnight = (rightNow + timedelta(days = 1)).replace(hour = 0, minute = 0, second = 0, microsecond = 0)
    remainingTime = (midnight - rightNow).seconds
    print('WrdToday - now, today #, hours left', rightNow, getTodaysWordle(), remainingTime // 3600)
    remainingHours = remainingTime // 3600
    hoursString = singularPluralDecider('hour', 'hours', remainingHours)
    remainingMinutes = (remainingTime - remainingHours * 3600) // 60
    minutesString = singularPluralDecider('minute', 'minutes', remainingMinutes)
    await ctx.send('Standings for Wordle {0} so far!\n{1}\nThere\'s still {2} {3} and {4} {5} left to play today\'s Wordle!'.format(getTodaysWordle(), getStanding(False), remainingHours, hoursString, remainingMinutes, minutesString), embed = WORDLE_LINK)

@bot.command(name = 'Rankings')
async def getRankings(ctx):
    ranking = sorted(wordlePlayerSet, key = lambda player: player.wins, reverse = True)
    result = ''
    standing = 0
    previousPlayerWins = -1
    for player in ranking:
        if (player.wins != previousPlayerWins):
            previousPlayerWins = player.wins
            standing += 1
        result += str(standing) + ': ' + player.name
        result += ' - ' + str(player.wins) + ' '
        result += singularPluralDecider('win', 'wins', player.wins) + '\n'
    await ctx.send('Current Wordle rankings!\n{0}'.format('No one has ever played Wordle...' if result == '' else result))

@bot.command(name = 'Bot')
async def botInfo(ctx):
    daysAgo = (datetime.now(tz) - START).days
    await ctx.send('Started keeping track on Wordle {0} ({1} {2} ago)'.format(STARTING_WORDLE.days, daysAgo, singularPluralDecider('day', 'days', daysAgo)))

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
