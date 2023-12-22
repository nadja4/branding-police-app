function fetchDataAndUpdate() {
    // Rufen Sie die Flask-Route '/update_data' auf
    fetch('/update_data')
        .then(response => response.json())
        .then(data => {
            // Aktualisieren Sie den Inhalt mit den empfangenen Daten
            const dataElement = document.getElementById('data');
            dataElement.innerText = "Status: " + data.result;
            if (data.success == "true") {
                dataElement.className = 'form-label fw-bold fs-5 bg-success text-white';
            } 
            else {
                dataElement.className = 'form-label fw-bold fs-5';
            }
        })
        .catch(error => console.error('Fehler beim Aktualisieren der Daten:', error));
}
// Führen Sie fetchDataAndUpdate beim Laden der Seite aus
fetchDataAndUpdate();
// Führen Sie fetchDataAndUpdate alle 5 Sekunden aus
setInterval(fetchDataAndUpdate, 5000);