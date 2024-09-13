import requests
import asyncio
import json
import pandas as pd
from datetime import datetime
import discord
from discord.ext import commands

# Inicializace Discord klienta
intents = discord.Intents.default()
intents.message_content = True

client = commands.Bot(command_prefix="!", intents=intents)

# Funkce pro stažení souboru
def stahni_data():
    casOd = datetime.now().strftime("%d.%m.%Y 00:00:00")
    casDo = datetime.now().strftime("%d.%m.%Y 23:59:59")
    
    url = f"http://webohled.hasici-vysocina.cz/udalosti/reports/WP_PrehledUdalosti_XLS.crf?casOd={casOd}&casDo={casDo}&stavIndex=0&krajId=108&stavIds=210,400,410,420,430,440,500,510,520,600,610,620,700,710,750,760,780,800&typSouboru=xls"
    
    try:
        response = requests.get(url)
        response.raise_for_status() 
        with open("udalosti.xls", "wb") as file:
            file.write(response.content)
        print(f"[INFO] Soubor stažen a uložen jako 'udalosti.xls' v {datetime.now()}")
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Chyba při stahování souboru: {e}")
    except PermissionError:
        print("[ERROR] Nedostatečná oprávnění pro zápis do souboru 'udalosti.xls'.")

# Funkce pro načtení posledního záznamu z JSON souboru
def nacti_posledni_zasah():
    try:
        with open('posledni_zasah.json', 'r') as file:
            data = json.load(file)
        posledni_cas = data.get('cas_posledniho_zasahu', None)
        print(f"[INFO] Načten poslední čas zásahu z JSON: {posledni_cas}")
        return posledni_cas
    except FileNotFoundError:
        print("[WARNING] Soubor 'posledni_zasah.json' nebyl nalezen. Pravděpodobně první spuštění.")
        return None

# Funkce pro uložení posledního záznamu do JSON souboru
def uloz_posledni_zasah(cas):
    with open('posledni_zasah.json', 'w') as file:
        json.dump({'cas_posledniho_zasahu': cas}, file)
    print(f"[INFO] Uložen čas posledního zásahu do JSON: {cas}")

# Funkce pro zpracování souboru Excel a získání dat
def zpracuj_soubor():
    try:
        df = pd.read_excel('udalosti.xls', engine='xlrd')  
        zasahy = df.values.tolist()
        posledni_cas = nacti_posledni_zasah()
        nove_zasahy = []

        print("[INFO] Kontrola nových zásahů...")
        for zasah in zasahy:
            datum_zasahu = zasah[0] 
            if posledni_cas is None or datum_zasahu > posledni_cas:
                nove_zasahy.append(zasah)
                print(f"[NEW] Nový zásah nalezen: {datum_zasahu}")

        if not nove_zasahy:
            print("[INFO] Žádné nové zásahy nebyly nalezeny.")
        
        # Vrací počet zásahů a nové zásahy
        return len(zasahy), nove_zasahy[::-1] 

    except Exception as e:
        print(f"[ERROR] Chyba při zpracování souboru: {e}")
        return 0, []

# Funkce pro vytvoření Discord Embed zprávy
def create_embed(event):
    # Vybereme pouze potřebné sloupce (kontrola, zda má event alespoň 11 hodnot)
    if len(event) < 11:
        print(f'[ERROR] Očekáváno minimálně 11 hodnot, ale získáno {len(event)}: {event}')
        return None

    # Vytáhneme potřebné sloupce
    datum, stav, typ_udalosti, podtyp_udalosti, okres, obec, ulice, poznamka = event[0], event[1], event[2], event[3], event[5], event[6], event[8], event[10]

    icons = {
        'požár': '🔥',
        'technická pomoc': '🔧',
        'dopravní nehoda': '🚗',
        'únik nebezpečných látek': '⚠️'
    }

    icon = icons.get(typ_udalosti.lower(), '🚨')

    embed = discord.Embed(
        title=f'{icon} {typ_udalosti} {datum}',
        description=podtyp_udalosti,
        color=0xFF0000
    )
    embed.add_field(name='Stav', value=stav, inline=False)
    embed.add_field(name='Okres', value=okres, inline=True)
    embed.add_field(name='Obec', value=obec, inline=True)
    embed.add_field(name='Ulice', value=ulice if ulice else 'N/A', inline=True)
    embed.add_field(name='Poznámka pro média', value=poznamka if poznamka else 'N/A', inline=True)
    embed.set_footer(text='HZS Vysočina Výjezdy', icon_url='https://i.ibb.co/rHh4s6h/icon.jpg')

    print(f"[INFO] Embed zpráva vytvořena pro zásah: {datum}")
    return embed


# Funkce pro zasílání nových zásahů na Discord
async def posli_na_discord(nove_zasahy):
    channel = client.get_channel() 
    for zasah in nove_zasahy:
        embed = create_embed(zasah)
        if embed:
            await channel.send(embed=embed)
            uloz_posledni_zasah(zasah[0])  
            print(f"[INFO] Zpráva o zásahu odeslána na Discord: {zasah[0]}")

# Hlavní část kódu pro opakované stahování dat
@client.event
async def on_ready():
    print(f'[INFO] Přihlášen jako {client.user}')
    
    while True:
        print("[INFO] Začínám stahovat data...")
        stahni_data()  # Stáhne soubor
        print("[INFO] Začínám zpracovávat soubor...")
        pocet_zasahu, nove_zasahy = zpracuj_soubor()  
        
        # Aktualizace statusu bota s počtem zásahů
        activity = discord.Game(name=f"Počet výjezdů: {pocet_zasahu}")
        await client.change_presence(status=discord.Status.dnd, activity=activity)

        if nove_zasahy:
            print(f"[INFO] Nalezeno {len(nove_zasahy)} nových zásahů. Odesílám na Discord...")
            await posli_na_discord(nove_zasahy) 
        else:
            print("[INFO] Nebyly nalezeny žádné nové zásahy.")
        
        await asyncio.sleep(61)  

client.run('')
