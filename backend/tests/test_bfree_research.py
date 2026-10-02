import torch
from inference_pipeline.bfree_research import embedding_crops


def test_center_and_corner_order_matches_upstream():
    x=torch.arange(36).reshape(1,1,6,6)
    crops=embedding_crops(x,2,2)
    assert [c[0,0,0,0].item() for c in crops]==[14,0,24,28,4]
    assert all(c.shape==(1,1,2,2) for c in crops)


def test_small_embeddings_repeat_instead_of_zero_padding():
    x=torch.tensor([[[[1.,2.],[3.,4.]]]])
    crops=embedding_crops(x,3,3)
    expected=torch.tensor([[[[1.,2.,1.],[3.,4.,3.],[1.,2.,1.]]]])
    assert len(crops)==5
    assert all(torch.equal(c,expected) for c in crops)
