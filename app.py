import os

from flask import (Flask, redirect, render_template, request,
                   send_from_directory, url_for)

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from azure.storage.queue import QueueServiceClient
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

account_name = 'sabrandingpoliceapp'
account_url_blob = "https://sabrandingpoliceapp.blob.core.windows.net/"
container_name = "container-branding-police-app"
account_url_queue = "https://sabrandingpoliceapp.queue.core.windows.net/"
queue_name = 'queue-branding-police-app'

credentials = DefaultAzureCredential()

def get_blob_data():
    blob_name = 'sample3.txt'

    # set client to access azure storage container
    blob_service_client = BlobServiceClient(account_url= account_url_blob, credential= credentials)

    # get the container client 
    container_client = blob_service_client.get_container_client(container=container_name)

    # download blob data 
    blob_client = container_client.get_blob_client(blob= blob_name)

    data = blob_client.download_blob().readall().decode("utf-8")

    print(data)

def list_blob():

    # set client to access azure storage container
    blob_service_client = BlobServiceClient(account_url= account_url_blob, credential= credentials)

    # get the container client 
    container_client = blob_service_client.get_container_client(container=container_name)

    for blob in container_client.list_blobs():
        print(blob.name)


def get_multi_blob_data():

    # set client to access azure storage container
    blob_service_client = BlobServiceClient(account_url= account_url_blob, credential= credentials)

    # get the container client 
    container_client = blob_service_client.get_container_client(container=container_name)

    for blob in container_client.list_blobs():
        blob_client = container_client.get_blob_client(blob= blob.name)
        data = blob_client.download_blob().readall()
        print(data.decode("utf-8"))

def upload_blob(file):
   blob_service_client = BlobServiceClient(account_url= account_url_blob, credential= credentials)
   container_client = blob_service_client.get_container_client(container=container_name)

   # Upload power point file to storage
   data = file.read()
   blob_client = container_client.upload_blob(name=file.filename, data=data, overwrite=True)
   file_urls = [blob_client.url]

   # Upload results_xx.txt
   results_filename = "result_" + file.filename.split('.')[0] + ".txt"
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
   return file_urls



def get_sas_url():
    # set client to access azure storage container
    blob_service_client = BlobServiceClient(account_url=account_url_queue, credential=credentials)
    blob_client = blob_service_client.get_blob_client(container=container_name, blob="results_test_pp.txt")

    # Gültigkeitsdauer der SAS-URL festlegen (hier: 1 Stunde)
    sas_token = generate_blob_sas(
        blob_client.account_name,
        blob_client.container_name,
        blob_client.blob_name,
        credential=credentials,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(hours=1)
    )

    # Vollständige SAS-URL erstellen
    sas_url = f"{blob_client.url}?{sas_token}"
    return sas_url

def queue(queue_content):
    queue_service_client = QueueServiceClient(account_url=account_url_queue, credential=credentials)
    queue_client = queue_service_client.get_queue_client(queue_name)

    for element in queue_content:
        queue_client.send_message(element)



@app.route('/')
def index():
   print('Request for index page received')
   return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/results', methods = ['POST'])
def upload_file():
   print('Request for upload page received')
   f = request.files['file']
   search_for = request.form['search-string']
   file_urls = upload_blob(f)
   print('file uploaded successfully')
   queue_content = file_urls
   queue_content.append(search_for)
   queue(queue_content)
   print('Sent to queue')
   link = "testlink"
   return render_template('results.html', link=link)

@app.route('/results', methods = ['GET'])
def link_to_file():
    print("Test")
    #window.open("https://google.de")
    #print(get_sas_url())

if __name__ == '__main__':
   app.run()
