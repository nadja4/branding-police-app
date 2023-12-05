import os

from flask import (Flask, redirect, render_template, request,
                   send_from_directory, url_for)
import asyncio
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions, BlobClient
from azure.storage.queue import QueueServiceClient, BinaryBase64EncodePolicy, BinaryBase64DecodePolicy
from datetime import datetime, timedelta, timezone

import json

from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

account_name = 'sabrandingpoliceapp'
account_url_blob = "https://sabrandingpoliceapp.blob.core.windows.net/"
container_name = "container-branding-police-app"
account_url_queue = "https://sabrandingpoliceapp.queue.core.windows.net/"
queue_name = 'queue-branding-police-app'

credentials = DefaultAzureCredential()

def upload_blob(file):
   blob_service_client = BlobServiceClient(account_url= account_url_blob, credential= credentials)
   container_client = blob_service_client.get_container_client(container=container_name)

   # Upload power point file to storage
   data = file.read()
   blob_client = container_client.upload_blob(name=file.filename, data=data, overwrite=True)
   blob_properties = blob_client.get_blob_properties()
   upload_time = blob_properties['last_modified']
   file_urls = [blob_client.url]

   # Upload results_xx.txt
   results_filename = "results_" + file.filename.split('.')[0] + ".txt"
   results_f = open(results_filename, "w")
   results_f.write("Working on " + file.filename)
   results_f.close()

   #open and read the file after the overwriting:
   results_f = open(results_filename, "r")
   data = results_f.read()
   blob_client = container_client.upload_blob(name=results_filename, data=data, overwrite=True)
   file_urls.append(blob_client.url)
   results_f.close()
   os.remove(results_filename)
   return file_urls, results_filename, upload_time

def request_user_delegation_key(blob_service_client, start_time, expiry_time):
    return blob_service_client.get_user_delegation_key(key_start_time=start_time,key_expiry_time=expiry_time)

def create_user_delegation_sas_blob(blob_service_client, blob_client):
    # Create a SAS token that's valid for one day, as an example
    start_time = datetime.now(timezone.utc) - timedelta(minutes=1)
    expiry_time = start_time + timedelta(hours=1)

    user_delegation_key = request_user_delegation_key(blob_service_client, start_time, expiry_time)

    print(blob_client.container_name, blob_client.blob_name, blob_client.account_name)
    sas_token = generate_blob_sas(
        account_name=blob_client.account_name,
        container_name=blob_client.container_name,
        blob_name=blob_client.blob_name,
        user_delegation_key=user_delegation_key,
        permission=BlobSasPermissions(read=True),
        expiry=expiry_time,
        start=start_time
    )

    return sas_token

## TODO:
async def check_for_updates(link, upload_time):
    print("Entered check for updates")
    blob_client = BlobClient.from_blob_url(link)

    modified = False
    # Überprüfe, ob der Blob existiert
    if blob_client.exists():

        # Holen Sie die Metadaten des Blobs
        blob_properties = blob_client.get_blob_properties()

        # Extrahiere den letzten Änderungszeitpunkt (last modified time) aus den Metadaten
        last_modified_time = blob_properties['last_modified']

        if last_modified_time > upload_time:
            print("modified")
            return True
    await asyncio.sleep(1)

def get_sas_url(filename):
    # set client to access azure storage container
    blob_service_client = BlobServiceClient(account_url=account_url_blob, credential=credentials)

    blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)
    sas_token = create_user_delegation_sas_blob(blob_service_client, blob_client)      
    # The SAS token string can be appended to the resource URL with a ? delimiter
    # or passed as the credential argument to the client constructor
    sas_url = f"{blob_client.url}?{sas_token}"
    # Create a BlobClient object with SAS authorization
    blob_client_sas = blob_client.from_blob_url(blob_url=sas_url)

    return blob_client_sas.url

def queue(queue_content):
    queue_service_client = QueueServiceClient(account_url=account_url_queue, credential=credentials)
    queue_client = queue_service_client.get_queue_client(queue_name)

    # Setup Base64 encoding and decoding functions
    # This is necessary because of a bug in azure functions (see https://stackoverflow.com/questions/24524266/putting-message-into-azure-queue)
    queue_client.message_encode_policy = BinaryBase64EncodePolicy()
    queue_client.message_decode_policy = BinaryBase64DecodePolicy()
    
    message = {
        'search-string': queue_content[2],
        'results_url' : queue_content[1],
        'powerpoint_url' : queue_content[0]
    }
    
    message_string = json.dumps(message)
    message_bytes = message_string.encode('utf-8')
    queue_client.send_message(queue_client.message_encode_policy.encode(content=message_bytes))



@app.route('/')
def index():
   print('Request for index page received')
   return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/results', methods = ['POST'])
async def upload_file():
   print('Request for upload page received')
   f = request.files['file']
   search_for = request.form['search-string']
   file_urls, result_filename, upload_time = upload_blob(f)
   print('file uploaded successfully')
   queue_content = file_urls
   queue_content.append(search_for)
   queue(queue_content)
   print('Sent to queue')
   await check_for_updates(get_sas_url(result_filename), upload_time)
   return render_template('results.html', name=f.filename, text=search_for, filename=result_filename)

@app.route('/results/<filename>', methods = ['GET'])
def link_to_file(filename):
    link = get_sas_url(filename)
    return redirect(link)

if __name__ == '__main__':
   app.run()
