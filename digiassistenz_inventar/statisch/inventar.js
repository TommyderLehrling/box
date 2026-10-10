/* Inventar: Scannen im Browser (BarcodeDetector, Chromium/Android) mit Eingabefeld als Rückfall. */
(function () {
  "use strict";

  function nummerAusText(text) {
    var marke = "/inventar/s/";
    var stelle = text.indexOf(marke);
    var rest = stelle >= 0 ? text.slice(stelle + marke.length) : text;
    rest = rest.split("#")[0].split("?")[0].replace(/\/+$/, "");
    try { return decodeURIComponent(rest).trim(); } catch (e) { return rest.trim(); }
  }

  function weiter(abschnitt, text) {
    var nummer = nummerAusText(text);
    if (!nummer) { return false; }
    var ks = abschnitt.getAttribute("data-ks");
    window.location.href = "/inventar/s/" + encodeURIComponent(nummer) + (ks ? "?ks=" + encodeURIComponent(ks) : "");
    return true;
  }

  function eingabe(abschnitt) {
    var formular = document.getElementById("scan-eingabe");
    if (!formular) { return; }
    formular.addEventListener("submit", function (ereignis) {
      ereignis.preventDefault();
      weiter(abschnitt, document.getElementById("scan-nummer").value);
    });
  }

  function kamera(abschnitt) {
    var feld = document.getElementById("scan-kamera");
    var status = document.getElementById("scan-status");
    if (!feld || !("BarcodeDetector" in window) || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      if (status) { status.textContent = abschnitt.getAttribute("data-text-kamera-fehlt"); }
      return;
    }
    var detektor = new window.BarcodeDetector({ formats: ["qr_code"] });
    var video = document.getElementById("scan-video");
    navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false }).then(function (strom) {
      feld.hidden = false;
      video.srcObject = strom;
      video.play();
      var fertig = false;
      function schauen() {
        if (fertig) { return; }
        detektor.detect(video).then(function (treffer) {
          if (treffer.length && weiter(abschnitt, treffer[0].rawValue)) {
            fertig = true;
            strom.getTracks().forEach(function (spur) { spur.stop(); });
            return;
          }
          window.setTimeout(schauen, 250);
        }).catch(function () { window.setTimeout(schauen, 500); });
      }
      schauen();
    }).catch(function () {
      if (status) { status.textContent = abschnitt.getAttribute("data-text-kamera-fehlt"); }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var abschnitt = document.getElementById("scan");
    if (!abschnitt) { return; }
    eingabe(abschnitt);
    kamera(abschnitt);
  });
})();
