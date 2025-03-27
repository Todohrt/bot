import discord
import asyncio
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import random
import json
import os
from keep_alive import keep_alive

TOKEN = os.environ.get('TOKEN')  # Utilise le token depuis les secrets
if not TOKEN:
    print("⚠️ Le token n'est pas configuré dans les secrets!")
    exit(1)
    
keep_alive()  # Démarre le serveur web
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix=["!", "/"], intents=intents)

# Charger les questions depuis le fichier JSON
def charger_questions():
    try:
        if os.path.exists('questions.json'):
            with open('questions.json', 'r') as f:
                return json.load(f)
    except json.JSONDecodeError:
        print("Erreur de lecture du fichier questions.json, création d'une nouvelle liste")
    return []

# Sauvegarder les questions dans le fichier JSON
def sauvegarder_questions():
    with open('questions.json', 'w') as f:
        json.dump(questions, f, indent=2)

# Liste des questions sous forme de dictionnaire {question: réponse}
questions = charger_questions()
scores = {}  # Points hebdomadaires
total_scores = {}  # Points totaux
roles_config = {
    150: "Niveau 6",
    75: "Niveau 5",
    50: "Niveau 4",
    30: "Niveau 3",
    15: "Niveau 2",
    5: "Niveau 1"
}
current_question = None
current_answer = None
winners = set()

async def update_member_role(member, score):
    # Trouve le rôle le plus élevé que le membre mérite
    earned_role = None
    for points, role_name in sorted(roles_config.items(), reverse=True):
        if score >= points:
            role = discord.utils.get(member.guild.roles, name=role_name)
            if role:
                earned_role = role
                break
    
    if earned_role:
        # Retire tous les rôles de niveau
        for role_name in roles_config.values():
            role = discord.utils.get(member.guild.roles, name=role_name)
            if role and role in member.roles:
                await member.remove_roles(role)
        # Ajoute le nouveau rôle
        await member.add_roles(earned_role)
# Fonction pour envoyer un message au canal général
async def envoyer_message(canal, message):
    if canal:
        await canal.send(message)
# Fonction pour poser une question
def sauvegarder_scores():
    with open('scores.json', 'w') as f:
        json.dump({'weekly': scores, 'total': total_scores}, f)

def charger_scores():
    global scores, total_scores
    try:
        if os.path.exists('scores.json'):
            with open('scores.json', 'r') as f:
                data = json.load(f)
                scores = data.get('weekly', {})
                total_scores = data.get('total', {})
    except:
        scores = {}
        total_scores = {}

async def poser_question():
    global current_question, current_answer, winners
    # Ne pas lancer de nouvelle question si une est en cours
    if current_question is not None:
        return
    winners = set()  # Réinitialiser la liste des gagnants
    if not questions:
        return
    question_data = random.choice(questions)
    current_question, current_answer = question_data["question"], question_data["reponse"].lower()
    canal = discord.utils.get(bot.get_all_channels(), name="quiz")  # Canal dédié au quiz
    message_question = f"📢 **Question :** {current_question}"
    message_indice1 = f"🧐 **Indice 1 :** La réponse commence par `{current_answer[0]}` et finit par `{current_answer[-1]}`"
    message_indice2 = f"🔢 **Indice 2 :** La réponse a `{len(current_answer)}` lettres et `{len(current_answer.split())}` mot(s)."
    message_reponse = f"✅ **Réponse :** ||{current_answer}||"
    await envoyer_message(canal, message_question)
    await asyncio.sleep(900)  # Attendre 15 min
    await envoyer_message(canal, message_indice1)
    await asyncio.sleep(900)  # Attendre encore 15 min
    await envoyer_message(canal, message_indice2)
    await asyncio.sleep(900)  # Attendre encore 15 min
    await envoyer_message(canal, message_reponse)
    current_question, current_answer = None, None  # Réinitialisation
# Commande pour ajouter une question via Discord
@bot.command()
async def ajouter_question(ctx, *, contenu: str = None):
    if not contenu or '"' not in contenu:
        await ctx.send("❌ Format incorrect ! Utilise : `!ajouter_question \"question\" \"réponse\"`")
        return
    try:
        parts = contenu.split("\"")
        question = parts[1].strip()
        reponse = parts[3].strip()
        questions.append({"question": question, "reponse": reponse})
        sauvegarder_questions()
        await ctx.send(f"✅ Question ajoutée : {question}")
    except IndexError:
        await ctx.send("❌ Format incorrect ! Utilise : `!ajouter_question \"question\" \"réponse\"`")
# Commande pour voir le classement des scores
@bot.command()
async def classement(ctx):
    classement = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    message = "**🏆 Classement des scores :**\n"
    for i, (joueur, score) in enumerate(classement, 1):
        message += f"{i}. {joueur} - {score} points\n"
    await ctx.send(message)
# Commande pour tester une question immédiatement
@bot.command()
async def aide(ctx):
    help_text = """
**📚 Liste des commandes disponibles :**
`/help` - Affiche cette liste des commandes
`/ajouter_question "question" "réponse"` - Ajoute une nouvelle question
`/classement` - Affiche le classement hebdomadaire
`/classement_total` - Affiche le classement total
`/test_question` - Lance une question test immédiatement

**⏰ Questions automatiques :**
- Tous les jours à 12h00
- Tous les jours à 18h00
- Tous les jours à 20h00

**🎭 Système de rôles :**
Les rôles sont attribués automatiquement selon vos points totaux :
- Niveau 1 : 5 points
- Niveau 2 : 15 points
- Niveau 3 : 30 points
- Niveau 4 : 50 points
- Niveau 5 : 75 points
- Niveau 6 : 150 points
"""
    await ctx.send(help_text)

@bot.event
async def on_message(message):
    global current_answer, winners
    if message.author == bot.user or message.content.startswith('/'):
        return

    if current_answer and message.channel.name == "quiz":
        if str(message.author.id) in winners:
            await message.delete()
            await message.channel.send(f"{message.author.mention} Tu as déjà trouvé la bonne réponse pour cette question !")
            return

        import unicodedata
        
        def normalize_text(text):
            # Supprime les accents et met en minuscule
            text = ''.join(c for c in unicodedata.normalize('NFD', text)
                          if unicodedata.category(c) != 'Mn')
            # Supprime les espaces superflus et les caractères spéciaux
            text = ''.join(c.lower() for c in text if c.isalnum() or c.isspace())
            return text.strip()
            
        reponse_joueur = message.content.strip()
        await message.delete()  # Supprimer tous les messages des joueurs
        if normalize_text(reponse_joueur) == normalize_text(current_answer):
            # Met à jour les scores hebdomadaires et totaux
            scores[str(message.author.display_name)] = scores.get(str(message.author.display_name), 0) + 1
            total_scores[str(message.author.display_name)] = total_scores.get(str(message.author.display_name), 0) + 1
            winners.add(str(message.author.id))
            sauvegarder_scores()  # Sauvegarder après chaque mise à jour
            
            # Met à jour le rôle
            await update_member_role(message.author, total_scores[str(message.author.display_name)])
            
            await message.channel.send(f"🎉 Bravo {message.author.mention} ! Tu as trouvé la bonne réponse !")
        else:
            await message.channel.send(f"❌ {message.author.mention} Ce n'est pas la bonne réponse, retente ta chance !")

    await bot.process_commands(message)  # Permet aux commandes de fonctionner

@bot.command()
async def test_question(ctx):
    global current_answer, current_question
    if current_question is not None:
        await ctx.send("❌ Une question est déjà en cours !")
        return
    await poser_question()

@bot.event
async def on_ready():
    print(f"✅ {bot.user} est connecté !")
    # Planification des questions
    scheduler = AsyncIOScheduler(timezone="Europe/Paris")
    
    # Questions quotidiennes (heure de Paris)
    scheduler.add_job(poser_question, "cron", hour=12, minute=0)
    scheduler.add_job(poser_question, "cron", hour=18, minute=0)
    scheduler.add_job(poser_question, "cron", hour=20, minute=0)
    
    # Envoi du classement hebdomadaire le dimanche à 10h (heure de Paris)
    async def envoyer_classement():
        canal = discord.utils.get(bot.get_all_channels(), name="général")
        classement_data = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        message = "**🏆 Classement hebdomadaire des joueurs :**\n"
        for i, (joueur, score) in enumerate(classement_data, 1):
            message += f"{i}. {joueur} - {score} points\n"
        await canal.send(message)
    
    async def envoyer_classement_total():
        canal = discord.utils.get(bot.get_all_channels(), name="général")
        classement_data = sorted(total_scores.items(), key=lambda x: x[1], reverse=True)
        message = "**🏆 Classement mensuel total des joueurs :**\n"
        for i, (joueur, score) in enumerate(classement_data, 1):
            message += f"{i}. {joueur} - {score} points\n"
        await canal.send(message)

    # Réinitialisation hebdomadaire des scores
    async def reset_weekly_scores():
        global scores
        scores = {}

    scheduler.add_job(envoyer_classement, "cron", day_of_week="sun", hour=14, minute=0)
    scheduler.add_job(reset_weekly_scores, "cron", day_of_week="mon", hour=0, minute=0)
    scheduler.add_job(envoyer_classement_total, "cron", day="1", hour=12, minute=0)
    scheduler.start()

@bot.command()
async def classement_total(ctx):
    classement_data = sorted(total_scores.items(), key=lambda x: x[1], reverse=True)
    message = "**🏆 Classement total des joueurs :**\n"
    for i, (joueur, score) in enumerate(classement_data, 1):
        message += f"{i}. {joueur} - {score} points\n"
    await ctx.send(message)
# Charger les scores au démarrage
charger_scores()
# Lancer le bot
bot.run(TOKEN)
