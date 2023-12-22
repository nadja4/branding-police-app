document.getElementById('copyLinkBtn').addEventListener('click', function() {
    // Rufen Sie die URL aus dem Datenattribut ab
    var dynamicUrl = this.getAttribute('data-url');

    // Führen Sie die gewünschten Aktionen mit der URL aus
    copyLink(dynamicUrl);
});

function copyLink() {
    var linkInput = document.getElementById('myLink');
    linkInput.select();
    document.execCommand('copy');

    var info = document.getElementById('info');
    info.innerHTML = 'Link wurde kopiert: ' + linkInput.value;
    info.style.display = 'block';

    // Automatisches Ausblenden nach einigen Sekunden
    setTimeout(function () {
        info.style.display = 'none';
    }, 2000); // 2000 Millisekunden = 2 Sekunden
}