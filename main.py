from flask import Flask
import quart
from quart_discord import DiscordOAuth2Session, requires_authorization, Unauthorized
import quart_rate_limiter
from quart_rate_limiter.redis_store import RedisStore
from quart_cors import cors
import json
import asyncpg
import asyncio
import secrets
import uvloop
import sentry_sdk
from sentry_sdk.integrations.quart import QuartIntegration
import datetime

from blueprints.v1 import v1_api

# used between nginx and hypercorn ONLY
import os
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "true"

with open("config.json", "r") as f:
    config = json.load(f)

if config.get("SENTRY_DSN"):
    sentry_sdk.init(dsn=config["SENTRY_DSN"],
                    integrations=[QuartIntegration(transaction_style="url")],
                    traces_sample_rate=1.0,
                    send_default_pii=True)
app = quart.Quart(__name__)
app.register_blueprint(v1_api)
app = cors(app, allow_origin=config.get("CORS_ORIGIN"))

if config.get("REDIS_URI"):
    app.rate_limiter = quart_rate_limiter.RateLimiter(app, store=RedisStore(config["REDIS_URI"]))
else:
    app.rate_limiter = quart_rate_limiter.RateLimiter(app)

app.token_cache = dict()
app.usage_cache = dict()
app.db = None

async def init_postgres():
    if config.get("POSTGRES_URI"):
            app.db = await asyncpg.create_pool(config["POSTGRES_URI"])
            async with app.db.acquire() as conn:
                await conn.execute("CREATE TABLE IF NOT EXISTS tokens (token TEXT, id BIGINT, email TEXT);")
                await conn.execute("CREATE TABLE IF NOT EXISTS usage (endpoint TEXT, id BIGINT, count BIGINT);")
                for entry in (await conn.fetch("SELECT * FROM tokens;")):
                    app.token_cache[entry.get("id")] = entry.get("token")
    else:
        app.token_cache[246938839720001536] = "TESTING_PURPOSES"

app.logger.info("hi")

async def commit_usage_data():
    try:
        while True:
            # await asyncio.sleep(1800)
            await asyncio.sleep(10)
            # if not app.db:
            #     return
            async with quart.current_app.db.acquire() as connection:
                async with connection.transaction():
                    entries = []
                    to_del = []
                    current = await connection.fetch("SELECT * FROM usage;")
                    for usr in app.usage_cache:
                        for endpi in app.usage_cache[usr].values():
                            for row in current:
                                curr_ind = 0
                                if (row.get("endpoint") == endpi) and (row.get("id") == usr):
                                    curr_ind = row.get("count")
                                    to_del.append((row.get("endpoint"), row.get("id")))
                                entries.append((endpi, usr, app.usage_cache[usr][endpi]+curr_ind))
                    await connection.executemany("DELETE FROM usage WHERE endpoint=$1 AND id=$2;", to_del)
                    await connection.executemany("INSERT INTO usage VALUES ($1, $2, $3);", entries)
                app.logger.info(await connection.fetch("SELECT * FROM usage;"))
            await asyncio.sleep(100)
    except asyncio.CancelledError:
        pass

@app.before_serving
async def handle_tasks():
    app.add_background_task(init_postgres)
    app.add_background_task(commit_usage_data)

@app.after_serving
async def cleanup_tasks():
    for tsk in app.background_tasks:
        tsk.cancel()

async def gen_token(user):
    token = secrets.token_urlsafe(15)
    async with quart.current_app.db.acquire() as connection:
            async with connection.transaction():
                await connection.execute("DELETE FROM tokens WHERE id = $1;", user.id)
                await connection.execute("INSERT INTO tokens VALUES ($1, $2, $3);", token, user.id, user.email)
    app.token_cache[user.id] = token
    return token

app.gen_token = gen_token

# asyncio.get_event_loop().run_until_complete(init_postgres())
# app.add_background_task(init_postgres())

for k in config.keys():
    if k.startswith("APP_"):
        app.config[k.lstrip("APP_")] = config[k]

discord = DiscordOAuth2Session(app)
app.discord = discord

@app.before_request
async def before_request_sentry():
    ipa = quart.request.headers.get("X-Forwarded-For")
    user_data = {"ip_address": ipa}
    k = ipa
    if await discord.authorized:
        user = await discord.fetch_user()
        k = user.id
        user_data.update({"id": user.id, "username": str(user), "email": user.email})
    sentry_sdk.set_user(user_data)
    sentry_sdk.set_tag("User-Agent", quart.request.headers.get("User-Agent"))
    if app.usage_cache.get(k):
        if app.usage_cache[k].get(quart.request.path):
            app.usage_cache[k][quart.request.path] += 1
        else:
            app.usage_cache[k][quart.request.path] = 1
    else:
        app.usage_cache[k] = {quart.request.path: 1}
    # print(app.usage_cache)

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
    user = await discord.fetch_user()
    token = app.token_cache.get(user.id)
    # async with quart.current_app.db.acquire() as connection:
    #     token = (await connection.fetchrow("SELECT token FROM tokens WHERE id = $1", user.id)).get("token")
    if not token:
        token = await app.gen_token(user)
    return await quart.render_template("tokenpage.html", token=token)

@app.route("/demo/<end>")
@requires_authorization
async def demo(end):
    return f"{quart.request.url_root}{end}?{quart.request.query_string.decode()}".rstrip("?")

if __name__ == "__main__":
    uvloop.install()
    app.run(host="localhost", port=7777, debug=True)