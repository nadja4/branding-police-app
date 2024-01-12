import os

from flask import (
    Flask,
    render_template,
    request,
    send_from_directory,
    jsonify
)

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import (
    BlobServiceClient,
    generate_blob_sas,
    BlobSasPermissions,
    BlobClient,
)
from azure.storage.queue import (
    QueueServiceClient,
    BinaryBase64EncodePolicy,
    BinaryBase64DecodePolicy,
)
from datetime import datetime, timedelta, timezone

import json

app = Flask(__name__)

credentials = DefaultAzureCredential()

# Get the key vault url from env (locally) or application strings (in Azure)
vault_url = os.environ["AZURE_VAULT_URL"]

# Create secret_client to get or set secrets in key vault
secret_client = SecretClient(vault_url=vault_url, credential=credentials)

account_name = secret_client.get_secret("StorageAccountName").value
account_url_blob = secret_client.get_secret("AccoutUrlBlob").value
container_name = secret_client.get_secret("StorageContainerName").value
queue_name = secret_client.get_secret("StorageQueueName").value
account_url_queue = secret_client.get_secret("StorageQueueUrl").value

def upload_blob(file):
    blob_service_client = BlobServiceClient(
        account_url=account_url_blob, credential=credentials
    )
    container_client = blob_service_client.get_container_client(
        container=container_name
    )

    # Upload power point file to storage
    data = file.read()
    blob_client = container_client.upload_blob(
        name=file.filename, data=data, overwrite=True
    )
    blob_properties = blob_client.get_blob_properties()
    upload_time = blob_properties["last_modified"]
    file_urls = [blob_client.url]

    # Upload results_xx.txt
    results_filename = "results_" + file.filename.split(".")[0] + ".txt"
    results_f = open(results_filename, "w")
    results_f.write("Working on " + file.filename)
    results_f.close()

    # open and read the file after the overwriting:
    results_f = open(results_filename, "r")
    data = results_f.read()
    blob_client = container_client.upload_blob(
        name=results_filename, data=data, overwrite=True
    )
    file_urls.append(blob_client.url)
    results_f.close()
    os.remove(results_filename)
    return file_urls, results_filename, upload_time


# Create SAS url for blob storage
def request_user_delegation_key(blob_service_client, start_time, expiry_time):
    return blob_service_client.get_user_delegation_key(
        key_start_time=start_time, key_expiry_time=expiry_time
    )


def create_user_delegation_sas_blob(blob_service_client, blob_client):
    # Create a SAS token that's valid for one day, as an example
    start_time = datetime.now(timezone.utc) - timedelta(minutes=1)
    expiry_time = start_time + timedelta(hours=1)

    user_delegation_key = request_user_delegation_key(
        blob_service_client, start_time, expiry_time
    )

    sas_token = generate_blob_sas(
        account_name=blob_client.account_name,
        container_name=blob_client.container_name,
        blob_name=blob_client.blob_name,
        user_delegation_key=user_delegation_key,
        permission=BlobSasPermissions(read=True),
        expiry=expiry_time,
        start=start_time,
    )

    return sas_token


def get_sas_url(filename):
    # set client to access azure storage container
    blob_service_client = BlobServiceClient(
        account_url=account_url_blob, credential=credentials
    )

    blob_client = blob_service_client.get_blob_client(
        container=container_name, blob=filename
    )
    sas_token = create_user_delegation_sas_blob(blob_service_client, blob_client)
    # The SAS token string can be appended to the resource URL with a ? delimiter
    # or passed as the credential argument to the client constructor
    sas_url = f"{blob_client.url}?{sas_token}"
    # Create a BlobClient object with SAS authorization
    blob_client_sas = blob_client.from_blob_url(blob_url=sas_url)
    return blob_client_sas.url


# Send data to queue to trigger azure function
def queue(queue_content):
    queue_service_client = QueueServiceClient(
        account_url=account_url_queue, credential=credentials
    )
    queue_client = queue_service_client.get_queue_client(queue_name)

    # Setup Base64 encoding and decoding functions
    # This is necessary because of a bug in azure functions (see https://stackoverflow.com/questions/24524266/putting-message-into-azure-queue)
    queue_client.message_encode_policy = BinaryBase64EncodePolicy()
    queue_client.message_decode_policy = BinaryBase64DecodePolicy()

    # Convert queue_content to JSON format
    message = {
        "search-string": queue_content[2],
        "results_url": queue_content[1],
        "powerpoint_url": queue_content[0],
    }
    message_string = json.dumps(message)
    message_bytes = message_string.encode("utf-8")
    
    # Send message to queue
    queue_client.send_message(
        queue_client.message_encode_policy.encode(content=message_bytes)
    )


# Check whether the results file has been updated since uploading to determine the current status of the analysis
def check_for_updates(upload_time, link):
    # Check whether the queue is empty. If it is empty, the function has started to run
    queue_service_client = QueueServiceClient(
        account_url=account_url_queue, credential=credentials
    )
    queue_client = queue_service_client.get_queue_client(queue_name)
    properties = queue_client.get_queue_properties()
    count = properties.approximate_message_count
    if count > 0:
        return "Warte auf den Start der Azure Function.", "false"

    # Check if the results file has been updated since uploading
    blob_client = BlobClient.from_blob_url(link)
    if blob_client.exists():
        blob_properties = blob_client.get_blob_properties()

        last_modified_time = blob_properties["last_modified"]

        if last_modified_time > upload_time:
            return "Die Suche ist abgeschlossen. Die Datei wurde aktualisiert.", "true"
        else:
            return "Die Suche läuft.", "false"
        
@app.after_request
def add_security_headers(resp):
    resp.headers['Content-Security-Policy']=f"default-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self'; style-src 'self'; base-uri 'self'; form-action 'self'; object-src 'self' data:; frame-ancestors 'none'"
    return resp

@app.route("/")
def index():
    print("Request for index page received")
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


@app.route("/results", methods=["POST"])
def upload_file():
    global upload_time, link
    print("Request for upload page received")
    # Get data from html/website
    f = request.files["file"]
    search_for = request.form["search-string"]
    # Upload powerpoint to blob storage
    file_urls, result_filename, upload_time = upload_blob(f)
    print("File uploaded successfully to blob storage")
    # Collect content for the queue message
    queue_content = file_urls
    queue_content.append(search_for)
    queue(queue_content)
    link = get_sas_url(result_filename)
    return render_template(
        "results.html",
        name=f.filename,
        text=search_for,
        filename=result_filename,
        sas_url=link,
    )


@app.route("/update_data")
def update_data():
    # Check the current status every 5 seconds
    try:
        result, success = check_for_updates(upload_time, link)
    except NameError:
        result = "Es ist ein Fehler aufgetreten, bitte gehe zurück zur Startseite und versuche es erneut."
        success = "false"

    result_data = {"result": result, "success": success}
    return jsonify(result_data)


if __name__ == "__main__":
    app.run()
