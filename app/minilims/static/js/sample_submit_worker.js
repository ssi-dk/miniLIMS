/* xlsx.js (C) 2013-present SheetJS -- http://sheetjs.com */
/* uncomment the next line for encoding support */
importScripts('https://unpkg.com/xlsx/dist/xlsx.full.min.js');
postMessage({t:"ready"});

onmessage = function (oEvent) {
  var v;
  try {
    v = XLSX.read(oEvent.data.d, { type: oEvent.data.b ? 'binary' : 'base64', cellText: false, cellDates: true});
  } catch(e) { postMessage({t:"e",d:e.stack||e}); }
	postMessage({t:"xlsx", d:JSON.stringify(v)});
};
