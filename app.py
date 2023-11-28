import os

from flask import (Flask, redirect, render_template, request,
                   send_from_directory, url_for)

from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

### Blob storage
client_id = os.environ['AZURE_CLIENT_ID']
tenant_id = os.environ['AZURE_TENANT_ID']
client_secret = os.environ['AZURE_CLIENT_SECRET']
account_url = os.environ["AZURE_STORAGE_URL"]

credentials = ClientSecretCredential(
    client_id = client_id, 
    client_secret= client_secret,
    tenant_id= tenant_id
)

def get_blob_data():
    container_name = os.environ['AZURE_CONTAINER_NAME']
    blob_name = 'sample3.txt'

    # set client to access azure storage container
    blob_service_client = BlobServiceClient(account_url= account_url, credential= credentials)

    # get the container client 
    container_client = blob_service_client.get_container_client(container=container_name)

    # download blob data 
    blob_client = container_client.get_blob_client(blob= blob_name)

    data = blob_client.download_blob().readall().decode("utf-8")

    print(data)

def list_blob():
    container_name = os.environ['AZURE_CONTAINER_NAME']

    # set client to access azure storage container
    blob_service_client = BlobServiceClient(account_url= account_url, credential= credentials)

    # get the container client 
    container_client = blob_service_client.get_container_client(container=container_name)

    for blob in container_client.list_blobs():
        print(blob.name)


def get_multi_blob_data():
    container_name = os.environ['AZURE_CONTAINER_NAME']

    # set client to access azure storage container
    blob_service_client = BlobServiceClient(account_url= account_url, credential= credentials)

    # get the container client 
    container_client = blob_service_client.get_container_client(container=container_name)

    for blob in container_client.list_blobs():
        blob_client = container_client.get_blob_client(blob= blob.name)
        data = blob_client.download_blob().readall()
        print(data.decode("utf-8"))

def upload_blob(file):
   container_name = os.environ['AZURE_CONTAINER_NAME']
   blob_service_client = BlobServiceClient(account_url= account_url, credential= credentials)
   container_client = blob_service_client.get_container_client(container=container_name)

   # Upload power point file to storage
   data = file.read()
   blob_client = container_client.upload_blob(name=file.filename, data=data, overwrite=True)

   # Upload results_xx.txt
   results_filename = "result_" + file.filename.split('.')[0] + ".txt"
   results_f = open(results_filename, "w")
   results_f.write("Working on " + file.filename)
   results_f.close()

   #open and read the file after the overwriting:
   results_f = open(results_filename, "r")
   data = results_f.read()
   blob_client = container_client.upload_blob(name=results_filename, data=data, overwrite=True)
   results_f.close()
   os.remove(results_filename)


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
   upload_blob(f)
   print('file uploaded successfully')
   link = "testlink"
   return render_template('results.html', link=link)

if __name__ == '__main__':
   app.run()
