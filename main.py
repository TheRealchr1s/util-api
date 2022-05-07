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
app.db = asyncio.get_event_loop().run_until_complete(asyncpg.create_pool(config["POSTGRES_URI"]))

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

@app.route("/demo")
@requires_authorization
async def demo():
    return "wip"

if __name__ == "__main__":
    app.run(host="localhost", port=7777, debug=True)