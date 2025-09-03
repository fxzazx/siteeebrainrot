import sqlite3
import threading
from flask import Flask, request, render_template_string, redirect, url_for
import discord
from discord.ext import commands
from discord import ButtonStyle, Interaction, PermissionOverwrite
from discord.ui import Button, View

# -----------------
# Configuração DB
# -----------------
conn = sqlite3.connect('store.db', check_same_thread=False)
cursor = conn.cursor()

# Verificar e atualizar o esquema do banco de dados
cursor.execute("PRAGMA table_info(products)")
columns = [info[1] for info in cursor.fetchall()]
if 'creator_name' not in columns:
    cursor.execute("ALTER TABLE products ADD COLUMN creator_name TEXT")
if 'creator_id' not in columns:
    cursor.execute("ALTER TABLE products ADD COLUMN creator_id INTEGER")
if 'status' not in columns:
    cursor.execute("ALTER TABLE products ADD COLUMN status TEXT DEFAULT 'pending'")
cursor.execute('''CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    price REAL,
    description TEXT,
    image_url TEXT,
    creator_name TEXT,
    creator_id INTEGER,
    status TEXT DEFAULT 'pending'
)''')
conn.commit()

# -----------------
# Configuração Flask
# -----------------
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BrainRot Shop</title>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Roboto', sans-serif; margin: 0; background: #f4f7fa; color: #333; }
        header { background: linear-gradient(135deg, #5865f2, #4752c4); padding: 40px 20px; color: white; text-align: center; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
        h1 { margin: 0; font-size: 2.5em; }
        .container { max-width: 1200px; margin: auto; padding: 20px; }
        .search-box { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 30px; background: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        input, button { padding: 12px; border-radius: 5px; border: 1px solid #ddd; flex: 1; min-width: 200px; }
        button { background: #5865f2; color: white; border: none; cursor: pointer; transition: background 0.3s; }
        button:hover { background: #4752c4; }
        .products { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 25px; }
        .product { background: white; border-radius: 15px; padding: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-align: center; transition: transform 0.3s, box-shadow 0.3s; }
        .product:hover { transform: translateY(-5px); box-shadow: 0 6px 20px rgba(0,0,0,0.15); }
        .product img { max-width: 100%; border-radius: 10px; margin-bottom: 15px; height: 200px; object-fit: cover; border: 1px solid #eee; }
        .product h2 { font-size: 1.4em; margin: 10px 0; color: #5865f2; }
        .product p { margin: 8px 0; font-size: 1em; }
        .buy-btn { background: #43b581; color: white; padding: 12px; border: none; border-radius: 5px; cursor: pointer; width: 100%; font-weight: bold; transition: background 0.3s; }
        .buy-btn:hover { background: #369b6d; }
        #loading { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(255,255,255,0.8); display: flex; justify-content: center; align-items: center; z-index: 1000; }
        .spinner { border: 8px solid #f3f3f3; border-top: 8px solid #5865f2; border-radius: 50%; width: 60px; height: 60px; animation: spin 1s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div id="loading">
        <div class="spinner"></div>
    </div>
    <header>
        <h1>BrainRot Shop</h1>
        <p>Encontre os melhores produtos com segurança e facilidade</p>
    </header>
    <div class="container">
        <form method="get" action="/">
            <div class="search-box">
                <input type="text" name="q" placeholder="Buscar produto" value="{{q}}">
                <input type="number" step="0.01" name="min_price" placeholder="Preço mínimo" value="{{min_price}}">
                <input type="number" step="0.01" name="max_price" placeholder="Preço máximo" value="{{max_price}}">
                <button type="submit">Filtrar</button>
            </div>
        </form>
        <div class="products">
        {% for product in products %}
            <div class="product">
                <img src="{{product[4] or 'https://via.placeholder.com/280x200'}}" alt="Imagem">
                <h2>{{product[1]}}</h2>
                <p><b>Preço:</b> R$ {{product[2]}}</p>
                <p>{{product[3]}}</p>
                <p><b>Vendedor:</b> {{product[5]}}</p>
                <form method="post" action="/buy/{{product[0]}}">
                    <button class="buy-btn" type="submit">Comprar</button>
                </form>
            </div>
        {% endfor %}
        </div>
    </div>
    <script>
        window.addEventListener('load', function() {
            document.getElementById('loading').style.display = 'none';
        });
    </script>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    q = request.args.get("q", "")
    min_price = request.args.get("min_price", "")
    max_price = request.args.get("max_price", "")

    query = "SELECT id, name, price, description, image_url, creator_name FROM products WHERE status = 'approved' AND 1=1"
    params = []

    if q:
        query += " AND name LIKE ?"
        params.append(f"%{q}%")
    if min_price:
        query += " AND price >= ?"
        params.append(float(min_price))
    if max_price:
        query += " AND price <= ?"
        params.append(float(max_price))

    cursor.execute(query, params)
    products = cursor.fetchall()

    return render_template_string(HTML_TEMPLATE, products=products, q=q, min_price=min_price, max_price=max_price)

@app.route("/buy/<int:product_id>", methods=["POST"])
def buy(product_id):
    cursor.execute("SELECT * FROM products WHERE id=?", (product_id,))
    product = cursor.fetchone()
    if product:
        bot.loop.create_task(create_ticket(product))
    return redirect(url_for("index"))

# -----------------
# Configuração Discord Bot
# -----------------
TOKEN = "MTQxMjg1NDgwOTc2MTE1NzI2Mw.G-jjoN.smm0p-xf3dO9eDg6MRdxeAW908oiIVERajpeAA"
GUILD_ID = 1412135078137430016  # ID do servidor
TICKET_CATEGORY = 1412135078687146006  # ID da categoria para tickets
PRODUCT_CREATION_CATEGORY = 1412135078687146007  # ID da categoria para criação de produtos
TARGET_CHANNEL = 1412517948987408549  # ID do canal para enviar o botão
APPROVAL_CHANNEL_ID = 1412863975015845888  # Canal para aprovações
ADMIN_ID = 1411772881636950046  # ID do admin que pode aprovar

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Armazenamento temporário para criação de produtos
product_creation_data = {}

class ProductButton(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Criar Produto", style=ButtonStyle.primary, custom_id="create_product_button")
    async def create_product(self, interaction: Interaction, button: Button):
        guild = bot.get_guild(GUILD_ID)
        if not guild or interaction.guild_id != GUILD_ID:
            await interaction.response.send_message("Este comando só pode ser usado no servidor correto!", ephemeral=True)
            return
        
        category = guild.get_channel(PRODUCT_CREATION_CATEGORY)
        if not category:
            print("Categoria de criação de produtos não encontrada.")
            return
        
        overwrites = {
            guild.default_role: PermissionOverwrite(view_channel=False),
            guild.me: PermissionOverwrite(view_channel=True),
            interaction.user: PermissionOverwrite(view_channel=True)
        }
        channel = await guild.create_text_channel(
            name=f"produto-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )
        product_creation_data[channel.id] = {"user_id": interaction.user.id, "creator_id": interaction.user.id, "creator_name": interaction.user.display_name, "step": "name"}
        await channel.send(
            embed=discord.Embed(
                title="📝 Criação de Novo Produto - Passo 1",
                description=f"{interaction.user.mention}, por favor, digite o **nome** do produto.",
                color=discord.Color.blue()
            ).set_footer(text="Responda com o nome do produto")
        )
        await interaction.response.send_message(f"Ticket de criação de produto aberto em {channel.mention}!", ephemeral=True)

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    channel = bot.get_channel(TARGET_CHANNEL)
    if channel:
        embed = discord.Embed(
            title="🛒 Loja Discord - Criar Produto",
            description="Clique no botão abaixo para abrir um ticket e criar um novo produto!",
            color=discord.Color.purple()
        )
        embed.set_footer(text="Sistema de Loja Automatizado")
        view = ProductButton()
        await channel.send(embed=embed, view=view)
    else:
        print("Canal alvo não encontrado. Verifique o TARGET_CHANNEL.")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild or message.guild.id != GUILD_ID:
        return
    
    if message.channel.id in product_creation_data:
        data = product_creation_data[message.channel.id]
        if message.author.id != data["user_id"]:
            return
        
        step = data["step"]
        
        if step == "name":
            data["name"] = message.content.strip()
            if not data["name"]:
                await message.channel.send(
                    embed=discord.Embed(
                        title="❌ Erro",
                        description="O nome não pode ser vazio.",
                        color=discord.Color.red()
                    )
                )
                return
            data["step"] = "price"
            await message.channel.send(
                embed=discord.Embed(
                    title="📝 Criação de Novo Produto - Passo 2",
                    description="Por favor, digite o **preço** do produto (ex: 29.99).",
                    color=discord.Color.blue()
                ).set_footer(text="Responda com o preço do produto")
            )
        
        elif step == "price":
            try:
                data["price"] = float(message.content)
                data["step"] = "description"
                await message.channel.send(
                    embed=discord.Embed(
                        title="📝 Criação de Novo Produto - Passo 3",
                        description="Por favor, digite a **descrição** do produto (ou deixe em branco para nenhuma).",
                        color=discord.Color.blue()
                    ).set_footer(text="Responda com a descrição ou deixe em branco")
                )
            except ValueError:
                await message.channel.send(
                    embed=discord.Embed(
                        title="❌ Erro",
                        description="Por favor, insira um preço válido (ex: 29.99).",
                        color=discord.Color.red()
                    )
                )
        
        elif step == "description":
            data["description"] = message.content.strip() if message.content.strip() else ""
            data["step"] = "image"
            await message.channel.send(
                embed=discord.Embed(
                    title="📝 Criação de Novo Produto - Passo 4",
                    description="Por favor, anexe uma **imagem** do produto (ou responda sem anexo para nenhuma).",
                    color=discord.Color.blue()
                ).set_footer(text="Anexe uma imagem ou responda qualquer coisa sem anexo")
            )
        
        elif step == "image":
            image_url = message.attachments[0].url if message.attachments else ""
            cursor.execute("INSERT INTO products (name, price, description, image_url, creator_name, creator_id, status) VALUES (?, ?, ?, ?, ?, ?, 'pending')", 
                          (data["name"], data["price"], data["description"], image_url, data["creator_name"], data["creator_id"]))
            conn.commit()
            product_id = cursor.lastrowid
            await message.channel.send(
                embed=discord.Embed(
                    title="✅ Produto Enviado para Aprovação",
                    description=f"Produto **{data['name']}** enviado para aprovação.\n"
                               f"ID: {product_id}\n"
                               f"**Preço:** R$ {data['price']:.2f}\n"
                               f"**Descrição:** {data['description'] or 'Sem descrição'}\n"
                               f"**Imagem:** {image_url or 'Sem imagem'}\n"
                               f"**Vendedor:** {data['creator_name']}",
                    color=discord.Color.green()
                )
            )
            # Enviar para canal de aprovação
            approval_channel = bot.get_channel(APPROVAL_CHANNEL_ID)
            if approval_channel:
                embed = discord.Embed(
                    title="🆕 Novo Produto Pendente",
                    description=f"ID: {product_id}\n"
                               f"**Nome:** {data['name']}\n"
                               f"**Preço:** R$ {data['price']:.2f}\n"
                               f"**Descrição:** {data['description'] or 'Sem descrição'}\n"
                               f"**Imagem:** {image_url or 'Sem imagem'}\n"
                               f"**Vendedor:** {data['creator_name']}",
                    color=discord.Color.orange()
                ).set_footer(text="Use !approve <id> para aprovar ou !reject <id> para rejeitar")
                await approval_channel.send(embed=embed)
            del product_creation_data[message.channel.id]
            await message.channel.delete()
        
        return
    
    await bot.process_commands(message)

@bot.command()
async def approve(ctx, product_id: int):
    if ctx.author.id != ADMIN_ID:
        await ctx.send("Você não tem permissão para usar este comando!")
        return
    cursor.execute("UPDATE products SET status = 'approved' WHERE id = ?", (product_id,))
    if cursor.rowcount > 0:
        conn.commit()
        await ctx.send(f"Produto ID {product_id} aprovado com sucesso!")
    else:
        await ctx.send(f"Produto ID {product_id} não encontrado.")

@bot.command()
async def reject(ctx, product_id: int):
    if ctx.author.id != ADMIN_ID:
        await ctx.send("Você não tem permissão para usar este comando!")
        return
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    if cursor.rowcount > 0:
        conn.commit()
        await ctx.send(f"Produto ID {product_id} rejeitado e removido.")
    else:
        await ctx.send(f"Produto ID {product_id} não encontrado.")

@bot.command()
async def listproducts(ctx):
    if not ctx.guild or ctx.guild.id != GUILD_ID:
        await ctx.send("Este comando só pode ser usado no servidor correto!")
        return
        
    cursor.execute("SELECT id, name, price FROM products WHERE status = 'approved'")
    products = cursor.fetchall()
    if not products:
        await ctx.send(
            embed=discord.Embed(
                title="📋 Lista de Produtos",
                description="Nenhum produto aprovado.",
                color=discord.Color.red()
            )
        )
    else:
        msg = "\n".join([f"**{p[0]}** - {p[1]} (R$ {p[2]:.2f})" for p in products])
        await ctx.send(
            embed=discord.Embed(
                title="📋 Lista de Produtos",
                description=msg,
                color=discord.Color.blue()
            )
        )

async def create_ticket(product):
    await bot.wait_until_ready()
    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        print("Guild não encontrada. Verifique o GUILD_ID.")
        return
    category = guild.get_channel(TICKET_CATEGORY)
    if category is None:
        print("Categoria não encontrada. Verifique o TICKET_CATEGORY.")
        return
    creator = await guild.fetch_member(product[6])  # creator_id is index 6
    overwrites = {
        guild.default_role: PermissionOverwrite(view_channel=False),
        guild.me: PermissionOverwrite(view_channel=True),
        creator: PermissionOverwrite(view_channel=True)
    }
    channel = await guild.create_text_channel(
        name=f"pedido-{product[1].replace(' ', '-')}",
        category=category,
        overwrites=overwrites
    )
    embed = discord.Embed(
        title="🛍️ Novo Pedido",
        description=f"Um novo pedido foi criado!\n\n"
                   f"**Produto:** {product[1]}\n"
                   f"**Preço:** R$ {product[2]:.2f}\n"
                   f"**Descrição:** {product[3] or 'Sem descrição'}\n"
                   f"**Imagem:** {product[4] or 'Sem imagem'}\n"
                   f"**Vendedor:** {product[5]}",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=product[4] or "https://via.placeholder.com/150")
    embed.set_footer(text="Sistema de Loja Automatizado")
    await channel.send(embed=embed)

# -----------------
# Thread para rodar Flask + Bot
# -----------------
def run_flask():
    app.run(host="0.0.0.0", port=5000, use_reloader=False)

def run_bot():
    bot.run(TOKEN)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    run_bot()
