import os
import io
import json

samplesheets_fail = (
    [{"sampleid":"3","barcode":"ABE","emails":"emailtest.com"}],
    [{"sampleid":"5@","barcode":"ABG","organism":"E. coli_","emails":"email@test.com"}],
    [{"sampleid":"7","organism":"E. coli"}],
    [{"sampleid":"1","barcode":"ABC","organism":"E. coli","emails":"email@test.com"},{"sampleid":"2","barcode":"ABC","organism":"E. coli","emails":"email@test.com"}],
)

samplesheets_success = [{"sampleid":"1","barcode":"ABZ","organism":"E. coli","emails":"email@test.com","priority": "low"},{"sampleid":"2","barcode":"ABC","organism":"E. coli","priority": "high", "emails":"email@test.com"}]

errors = (
    {"errors": {"rows": {'1': ["Missing required column(s): ['organism']", 'Invalid value for field emails (emailtest.com)']}}},
    {"errors": {"rows": {'1': ['Invalid value for field sampleid (5@)', "Species E. coli_ not in database. Contact admin."]}}},
    {"errors": {"rows": {'1': ["Missing required column(s): ['barcode']"]}}},
    {"errors": {"general": ["Duplicate barcodes: ['ABC']"]}},
    {"errors":{}}
)

status_fail = "Fail"
status_ok = "OK"


dbentries_empty = []

dbentries_success = [
    {
        "barcode": "ABZ",
        "archived": False,
        "properties": {
            "sample_info":{
                "summary": {
                    "name": '1',
                    "submitter": "test",
                    "submitted_species_name": "Escherichia coli",
                    "submitted_species": "Escherichia coli",
                    "emails": ["email@test.com"],
                    "group": "TST",
                    "priority": 0,
                    '_cls': 'minilims.models.sample.S_summary'
                },
                '_cls': 'minilims.models.sample.S_info'
            },
            '_cls': 'minilims.models.sample.S_properties'
        },
        '_cls': 'minilims.models.sample.Sample'
    },
    {
        "barcode": "ABC",
        "archived": False,
        "properties": {
            "sample_info":{
                "summary": {
                    "name": '2',
                    "submitter": "test",
                    "submitted_species": "Escherichia coli",
                    "submitted_species_name": "Escherichia coli",
                    "emails": ['email@test.com'],
                    "group": "TST",
                    "priority": 4,
                    '_cls': 'minilims.models.sample.S_summary'
                },
                '_cls': 'minilims.models.sample.S_info'
            },
            '_cls': 'minilims.models.sample.S_properties'
        },
        '_cls': 'minilims.models.sample.Sample'
    },
]

steps = [
    ("test_step1A", "test_step1"),
    ("submit_to_bifrost", "submit_to_bifrost"),
    ("test_step2", "test_step2")
]

workflows = [
    {
        'name': 'workflow1',
        'display_name': 'workflow 1',
        'steps': ["test_step1A"],
        "valid_plate_types": [
            "96plate"
        ]
    },
    {
        'name': 'workflow2',
        'display_name': 'workflow 2',
        'steps': ["submit_to_bifrost"],
        "valid_plate_types": [
            "96plate"
        ]
    },
    {
        'name': 'workflow3',
        'display_name': 'workflow 3',
        'steps': ["test_step1A", "test_step2"],
        "valid_plate_types": [
            "96plate"
        ]
    },
    {
        'name': 'wgs_routine',
        'display_name': 'WGS routine [DRAFT]',
        'steps': [
            "wgs_01_dna_extraction",
            "wgs_02_quantification_1",
            "wgs_02-5_qc_1",
            "wgs_03_dillution_1",
            "wgs_04_quantification_2",
            "wgs_05_dillution_2",
            "wgs_05-5_qc_2",
            "wgs_06_library_prep",
            "wgs_07_quantification_postlib",
            "wgs_08_normalization_pool",
            "wgs_09_sequencing",
            "wgs_10_send_to_bifrost"
        ],
        "valid_plate_types": [
            "96plate"
        ]
    }
]

batch_name = "Batch01"

assign_samples = [
    {
        "sample_barcodes": ["ABZ","ABC"],
        "workflow": "workflow1",
        "batch_name": batch_name,
        "plate_type": "96plate"
    }
]

barcodes = [
    ("ABZ", "ABC")
]



attached = {
    'none': {},
    'in1': {"params": '{"all": {"in1": 123123}}'},
    'illu': {'samplesheet_csv': (io.BytesIO(b"This is the placeholder for an illumina file"), "filename.csv")},
    # Same as illu, but it can only be used for one test.
    'illu2': {'samplesheet_csv': (io.BytesIO(b"This is the placeholder for an illumina file"), "filename.csv")},
    'illu3': {'samplesheet_csv': (io.BytesIO(b"This is the placeholder for an illumina file"), "filename.csv")}
}
