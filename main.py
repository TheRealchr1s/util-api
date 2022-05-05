import quart
from quart_discord import DiscordOAuth2Session, requires_authorization, Unauthorized
import json

from blueprints.v1 import v1_api

# dev env only
import os
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "true"
# REMOVE IN PROD

with open("config.json", "r") as f:
    config = json.load(f)

app = quart.Quart(__name__)
app.register_blueprint(v1_api)

for k in config.keys():
    app.config[k] = config[k]

discord = DiscordOAuth2Session(app)
app.discord = discord

@app.errorhandler(Unauthorized)
async def redirect_unauthorized(e):
    return await discord.create_session()

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
    return await quart.render_template("tokenpage.html", authtoken=user["access_token"])

if __name__ == "__main__":
    app.run(host="localhost", port=7777, debug=True)