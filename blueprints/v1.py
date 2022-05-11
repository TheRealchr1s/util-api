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
    user = await quart.current_app.discord.fetch_user()
    token = await quart.current_app.gen_token(user)
    return quart.Response(json.dumps({"t": token}), mimetype="application/json")