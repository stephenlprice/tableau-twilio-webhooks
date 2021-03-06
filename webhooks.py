import os, datetime, uuid
from dotenv import load_dotenv
from flask import Flask, request, redirect, url_for
import tableauserverclient as TSC
from tableauserverclient.models.pagination_item import PaginationItem
from twilio.rest import Client
import jwt

# load environment files from .env
load_dotenv("./.env")
# calling environ is expensive, this saves environment variables to a dictionary
env_dict = dict(os.environ)
# dictionary with required environment variables
env_vars = [
  "TABLEAU_USERNAME",
  "TABLEAU_PAT_NAME", 
  "TABLEAU_PAT_SECRET",
  "TABLEAU_CA_CLIENT",
  "TABLEAU_CA_SECRET_ID",
  "TABLEAU_CA_SECRET_VALUE", 
  "TABLEAU_SITENAME", 
  "TABLEAU_SERVER",
  "TWILIO_ACCOUNT_SID",
  "TWILIO_AUTH_TOKEN",
  "TWILIO_FROM_NUMBER",
  "TWILIO_TO_NUMBER",
  "WHATSAPP_FROM",
  "WHATSAPP_TO"
]

# check that each environment variable is available, else throw an exception
for vars in env_vars:
  try:
      # check the local dictionary pulled from os.environ
      env_dict[vars]
  except KeyError:
    # output the first environment variable to fail and shut the server down
    raise RuntimeError(f"Environment variable {vars} is not available, server shutting down...")

# tableau connected app variables (JWT) see: https://help.tableau.com/current/online/en-us/connected_apps.htm#step-3-configure-the-jwt
header_data = {
  "iss": env_dict["TABLEAU_CA_CLIENT"],
  "kid": env_dict["TABLEAU_CA_SECRET_ID"],
  "alg": "HS256",
}

payload_data = {
  "iss": env_dict["TABLEAU_CA_CLIENT"],
  "sub": env_dict["TABLEAU_USERNAME"],
  "aud": "tableau",
  "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=5),
  "jti": str(uuid.uuid4()),
  "scp": ["tableau:content:read", "tableau:workbooks:create"]
}

connected_app_secret = env_dict["TABLEAU_CA_SECRET_VALUE"]

# twilio variables
twilioSID = env_dict["TWILIO_ACCOUNT_SID"]
twilioAuthToken = env_dict["TWILIO_AUTH_TOKEN"]
twilioClient = Client(twilioSID, twilioAuthToken)
fromNumber = env_dict["TWILIO_FROM_NUMBER"]
toNumber = env_dict["TWILIO_TO_NUMBER"]
fromWhatsApp = env_dict["WHATSAPP_FROM"]
toWhatsApp = env_dict["WHATSAPP_TO"]

# initiate the Flask instance
app = Flask(__name__)

# an API index listing supported endpoints and methods
@app.route("/")
def index():
    return '<h1>Notifier API Index</h1>\n<ul><li>/notifier <strong>POST</strong> - receives incoming Tableau Server webhooks to create datasource failure notifications</li></ul>'

# handles updating views on tableau broadcast once workbooks are refreshed on tableau cloud
@app.route("/broadcast", methods=["GET", "POST"])
def broadcast():
  print(request)
  if request.method == "POST":
    print(request)

    # encode the JWT with declared payload, secret and headers
    token = jwt.encode(
      payload = payload_data,
      key = connected_app_secret,
      headers = header_data
    )
    print(f'encoded token: {token}')

    # decode the JWT for testing purposes
    decodedToken = jwt.decode(
      jwt = token, 
      key = connected_app_secret,
      audience = payload_data["aud"], 
      algorithms = header_data["alg"]
    )
    print(f'decoded token: {decodedToken}')

    return "200 SUCCESS"

  elif request.method == "GET":
    # GET requests redirects to index "/" to display a list of supported API endpoints
    return redirect(url_for("index"))

  else:
    # any other methods are not supported
    return "400 Bad Request: method not supported"

# handles notifications for failed data source refreshes
@app.route("/notifier", methods=["GET", "POST"])
def notify():
    print(request)
    if request.method == "POST":
        # creates an authorization object using environment variables
        tableauAuth = TSC.PersonalAccessTokenAuth(env_dict["TABLEAU_PAT_NAME"], env_dict["TABLEAU_PAT_SECRET"], env_dict["TABLEAU_SITENAME"])
        # server object using environment variables
        server = TSC.Server(env_dict["TABLEAU_SERVER"])
        # append response data to log.txt
        with open("log.txt", "a") as logFile:
          # using now() to get current time for timestamp
          current_time = datetime.datetime.now()
          # server object signs in and fetches a list of datasources
          with server.auth.sign_in(tableauAuth):
            allDatasources, PaginationItem = server.datasources.get()
            # append each 
            logFile.write(f"\n{current_time}: There are {PaginationItem.total_available} datasources on site\n")
        
            # loop through datasources on site to output an individual detail
            for dataSource in allDatasources:
              # append each datasource to the log file
              msgStr = f"Datasource Refresh failed\n\tName:{dataSource.name}\n\tDescription:{dataSource.description}\n\tLast updated: {dataSource.updated_at}\n"
              logFile.write(msgStr)

              # implementing SMS, WhatsApp and Phone call Twilio services along with logs
              textMessage = twilioClient.messages.create(
                body = msgStr,
                from_ = fromNumber,
                to = toNumber
              )
              logFile.write(f"Text message SID: {textMessage.sid}\nSending SMS message from {fromNumber} to {toNumber}\n")

              whatsappMessage = twilioClient.messages.create(
                body = msgStr,
                from_ = fromWhatsApp,
                to = toWhatsApp
              )
              logFile.write(f"Whatsapp message SID: {whatsappMessage.sid}\nSending Whatsapp message from {fromWhatsApp} to {toWhatsApp}\n")

              call = twilioClient.calls.create(
                twiml = f"<Response><Say>{msgStr}</Say></Response>",
                from_ = fromNumber,
                to = toNumber 
              )
              logFile.write(f"Call SID: {call.sid}\nAutomated call from {fromNumber} to {toNumber}\n")

        return "200 SUCCESS"

    elif request.method == "GET":
      # GET requests redirects to index "/" to display a list of supported API endpoints
      return redirect(url_for("index"))

    else:
      # any other methods are not supported
      return "400 Bad Request: method not supported"

if __name__ == "__main__":
  app.run()
