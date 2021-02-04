var pending = false;
var rABS = typeof FileReader !== "undefined" && typeof FileReader.prototype !== "undefined" && typeof FileReader.prototype.readAsBinaryString !== "undefined";
function xw(data, cb) {
  pending = true;
  spinner = new Spinner().spin(document.getElementById("submitDiv"));
  var worker = new Worker('/static/js/sample_submit_worker.js');
  worker.onmessage = function (e) {
    switch (e.data.t) {
      case 'ready': break;
      case 'e': pending = false; console.error(e.data.d); break;
      case 'xlsx': cb(JSON.parse(e.data.d)); break;
    }
  };
  var arr = rABS ? data : btoa(fixdata(data));
  worker.postMessage({ d: arr, b: rABS });
}
var file = document.getElementById('file')

function validateTable() {
  var count = table.rows().count();
  updateCount(count);
  if (count === 0) {
    document.getElementById('errors').innerHTML = "";
    return
  }
  var tableHTML = document.getElementById('data-table');
  var ws = XLSX.utils.table_to_sheet(tableHTML);
  var json = XLSX.utils.sheet_to_json(ws, { dateNF: 'dd"."mm"."yyyy',})
  submitForValidation(json);
}
function submitButton() {
  var tableHTML = document.getElementById('data-table');
  var ws = XLSX.utils.table_to_sheet(tableHTML);
  var json = XLSX.utils.sheet_to_json(ws, { dateNF: 'dd"."mm"."yyyy',})
  submitSamples(json);
}


// document.getElementById("validate_table").addEventListener("click", validateTable)
document.getElementById("submit_table").addEventListener("click", submitButton)

/**
 * Default callback for insertion: mock webservice, always success.
 */
function onAddRow(dt, rowdata, success, error) {
  success(rowdata);
  validateTable();
}

/**
 * Default callback for editing: mock webservice, always success.
 */
function onEditRow(dt, rowdata, success, error) {
  success(rowdata);
  validateTable();
}

/**
 * Default callback for deletion: mock webservice, always success.
 */
function onDeleteRow(dt, rowdata, success, error) {
  success(rowdata);
  validateTable();
}

var table = $('#data-table').DataTable({
  paging: false,
  columns: columns, //This variable comes from submit.html scripts section (template)
  // columnDefs: [{
  //   orderable: false,
  //   className: 'select-checkbox',
  //   targets: 0
  // }],
  select: {
    style: 'os',
    // selector: 'td:first-child'
  },
  // order: [[1, 'asc']],
  deferRender: true,
  // scrollY: 700,
  // scrollCollapse: true,
  // scroller: true,
  dom: 'Bfrtip',
  altEditor: true, //Enable alteditor
  onEditRow: onEditRow,
  // onDeleteRow: onDeleteRow,
  onAddRow: onAddRow,
  buttons: [
    {
      text: 'Add',
      name: 'add'        // do not change name
    },
    {
      extend: 'selected', // Bind to Selected row
      text: 'Edit',
      name: 'edit'        // do not change name
    },
    {
      // extend: 'selected', // Bind to Selected row
      text: 'Delete',
      name: 'delete_rows',  // do not change name
      action: function (e, dt, node, config) {
        dt.rows({ "selected": true }).remove().draw();
        validateTable();
      },
      enabled: false
    },
  ]
});

table.on("select deselect", function () {
  var selectedRows = table.rows({ selected: true }).count();
  table.button("delete_rows:name").enable(selectedRows > 0);
})


function activateTable(data) {
  table.rows.add(data).draw(false);
}

function displayErrors(errorstring) {
  var errors = JSON.parse(errorstring).errors;
  var warnings = JSON.parse(errorstring).warnings;
  errorpre = "";
  if (errors.general) {
    for (index in errors.general) {
      errorpre = errorpre + errors.general[index] + "\n"
    }
  }
  if (errors.rows) {
    for (row in errors.rows) {
      errorpre = errorpre + "Row " + row + ": " + errors.rows[row] + "\n"
    }
  }
  if (warnings.general) {
    for (index in warnings.general) {
      errorpre = errorpre + "Warning: " + warnings.general[index] + "\n"
    }
  }
  document.getElementById('errors').innerHTML = errorpre;
}

function isEmpty(obj) {
  for (var prop in obj) {
    if (obj.hasOwnProperty(prop)) {
      return false;
    }
  }

  return JSON.stringify(obj) === JSON.stringify({});
}

function toggleSubmit(errorstring) {
  var errors = JSON.parse(errorstring).errors;
  if (isEmpty(errors)) {
    document.getElementById('submit_table').disabled = false;
  } else {
    document.getElementById('submit_table').disabled = true;
  }
}

function submitSamples(json) {
  var xhr = new XMLHttpRequest;
  xhr.open('POST', '/samples/submit', true);
  xhr.setRequestHeader("Content-Type", "application/json;charset=UTF-8");

  xhr.onload = function () {
    if (this.status === 200) {
      var json = JSON.parse(this.responseText);
      if (json.status === "OK") {
        location.href = "/"
      }
      displayErrors(this.responseText)
    }
  }
  xhr.send(JSON.stringify(json));
}

function submitForValidation(json) {
  var xhr = new XMLHttpRequest;
  xhr.open('POST', '/samples/validate', true);
  xhr.setRequestHeader("Content-Type", "application/json;charset=UTF-8");

  xhr.onload = function() {
    if (this.status === 200) {
      displayErrors(this.responseText);
      toggleSubmit(this.responseText);
    } else {
      displayErrors(JSON.stringify({ "errors": { "general": ["Error validating file. If the problem persists, please contact admin."] } }));
      document.getElementById('submit_table').disabled = true;
    }
  }
  xhr.send(JSON.stringify(json));
}

function updateCount(l) {
  $("#selected-count").html(l);
}

function processWb(wb) {
  var json = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], { defval: null, dateNF: 'dd"."mm"."yyyy',})
  updateCount(json.length);
  submitForValidation(json);
  spinner.stop();
  activateTable(json);
  pending = false;
}


function handleFile(e) {
  if (pending) return alertify.alert('Please wait until the current file is processed.', function () { });
  var files = e.target.files;
  var i, f;
  for (i = 0, f = files[i]; i != files.length; ++i) {
    var reader = new FileReader();
    var name = f.name;
    reader.onload = function (e) {
      var data = e.target.result;
      var wb, arr;
      var readtype = { type: rABS ? 'binary' : 'base64' };
      if (!rABS) {
        arr = fixdata(data);
        data = btoa(arr);
      }
      function doit() {
        try {
          xw(data, processWb);
        } catch (e) {
          console.log(e);
          alertify.alert('We unfortunately dropped the ball here.  Please test the file using the <a href="/js-xlsx/">raw parser</a>.  If there are issues with the file processor, please send this file to <a href="mailto:dev@sheetjs.com?subject=I+broke+your+stuff">dev@sheetjs.com</a> so we can make things right.', function () { });
          pending = false;
        }
      }

      if (e.target.result.length > 1e6) alertify.confirm("This file is " + e.target.result.length + " bytes and may take a few moments.  Your browser may lock up during this process.  Shall we play?", function (k) { if (k) doit(); });
      else { doit(); }
    };
    if (rABS) reader.readAsBinaryString(f);
    else reader.readAsArrayBuffer(f);
  }
}


if (file.addEventListener) {
  file.addEventListener('change', handleFile, false)
}

