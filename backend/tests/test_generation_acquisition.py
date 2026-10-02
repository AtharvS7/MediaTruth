import base64
import io

import pytest
from PIL import Image

from fetch_generation_controls import decode_row


def test_preserves_exact_source_bytes():
    stream=io.BytesIO()
    Image.new('RGB',(20,30),'red').save(stream,format='PNG')
    raw=stream.getvalue()
    item={'row':{'label':0,'split':'test','image_data':base64.b64encode(raw).decode()}}
    row, data=decode_row(item)
    assert row['label']==0
    assert data==raw


def test_truncated_cells_never_become_evaluation_samples():
    with pytest.raises(ValueError,match='truncated'):
        decode_row({'truncated_cells':['image_data']})


@pytest.mark.parametrize('label,split', [(2,'test'),(0,'train')])
def test_rejects_wrong_labels_and_training_rows(label,split):
    with pytest.raises(ValueError,match='label or split'):
        decode_row({'row':{'label':label,'split':split}})
