import quart
from quart_discord import DiscordOAuth2Session, requires_authorization, Unauthorized
import quart_rate_limiter
from quart_rate_limiter.redis_store import RedisStore
import json
import asyncpg
import asyncio

from blueprints.v1 import v1_api

# used between nginx and hypercorn ONLY
import os
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "true"

with open("config.json", "r") as f:
    config = json.load(f)

app = quart.Quart(__name__)
app.register_blueprint(v1_api)
app.rate_limiter = quart_rate_limiter.RateLimiter(app, store=RedisStore(config["REDIS_URI"]))

async def init_postgres():
    app.db = await asyncpg.create_pool(config["POSTGRES_URI"])
    async with app.db.acquire() as conn:
        await conn.execute("CREATE TABLE IF NOT EXISTS tokens (token VARCHAR(15), id BIGINT);")

if config.get("POSTGRES_URI"):
    asyncio.get_event_loop().run_until_complete(init_postgres())

for k in config.keys():
    if k.startswith("APP_"):
        app.config[k.lstrip("APP_")] = config[k]

discord = DiscordOAuth2Session(app)
app.discord = discord

@app.errorhandler(Unauthorized)
async def redirect_unauthorized(e):
    return await discord.create_session(scope=["identify", "email"])

@app.route("/")
async def index():
    user = None
    if await discord.authorized:
        user = await discord.fetch_user()
    return await quart.render_template("index.html", user=user)

@app.route("/login")
async def login():
    return await discord.create_session(scope=["identify", "email"])

@app.route("/callback")
async def callback():
    await discord.callback()
    return quart.redirect(quart.url_for("index"))

@app.route("/token")
@requires_authorization
async def token_route():
    user = await discord.get_authorization_token()
    return await quart.render_template("tokenpage.html", authtoken=user["access_token"], token="Example")

@app.route("/demo/<end>")
@requires_authorization
async def demo(end):
    return f"{quart.request.url_root}{end}?{quart.request.query_string.decode()}".rstrip("?")

if __name__ == "__main__":
    app.run(host="localhost", port=7777, debug=True)