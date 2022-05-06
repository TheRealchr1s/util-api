import quart
from jinja2 import TemplateNotFound
import json
import datetime
import quart_discord
import quart_rate_limiter

v1_api = quart.Blueprint("v1", __name__, template_folder="../templates", url_prefix="/v1")

@v1_api.route("/reset-token", methods=["POST"])
@quart_discord.requires_authorization
@quart_rate_limiter.rate_limit(2, datetime.timedelta(minutes=5))
async def reset_token():
    provided = quart.request.headers.get("Authorization")
    actual = (await quart.current_app.discord.get_authorization_token())["access_token"]
    if provided == actual:
        return quart.Response(json.dumps({"t": "objxyz"}), mimetype="application/json")
    else:
        raise quart_discord.Unauthorized