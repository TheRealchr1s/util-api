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

@v1_api.route("/endpoint1")
@quart_rate_limiter.rate_limit(5, datetime.timedelta(minutes=1))
async def endpoint1():
    if not quart.request.headers.get("Authorization") in quart.current_app.token_cache.values():
        return quart.Response(json.dumps({"i": "", "e": "Unauthorized"}), mimetype="application/json", status=401)
    else:
        return quart.Response(json.dumps({"i": "https://example.com"}), mimetype="application/json")

@v1_api.after_request
async def postrequest_usage(response):
    app = quart.current_app
    if response.status_code != 200:
        return response
    # if not (await app.discord.authorized):
    #     return response
    app.logger.warn("hi")
    # user = await app.discord.fetch_user()
    usrid = list(app.token_cache.keys())[ list(app.token_cache.values()).index(quart.request.headers["Authorization"]) ]
    if app.usage_cache.get(usrid):
        if app.usage_cache[usrid].get(quart.request.path):
            app.usage_cache[usrid][quart.request.path] += 1
        else:
            app.usage_cache[usrid][quart.request.path] = 1
    else:
        app.usage_cache[usrid] = {quart.request.path: 1}

    return response