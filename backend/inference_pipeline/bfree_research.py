"""Nonprofit research adapter for B-Free; never a validated production verdict.

Adapted from grip-unina/B-Free code/networks/wrapper5crops.py at
c6a9f898782fb466b29af01f21960b67415afb0e.
Copyright (c) 2025 Image Processing Research Group of University Federico II
of Naples ('GRIP-UNINA'). All rights reserved. Nonprofit use only.
Original terms are in licenses/BFREE_LICENSE.txt. Modification: execute the
five embedding crops sequentially to bound CPU peak memory.
Reference: Guillaro et al., A Bias-Free Training Paradigm for More General
AI-generated Image Detection, CVPR 2025, pp. 18685-18694.
"""
import math

import torch
import timm


def embedding_crops(embeddings, height, width):
    """Match the upstream center and four corner crops, including wrap padding."""
    if embeddings.shape[-2] < height or embeddings.shape[-1] < width:
        embeddings = embeddings.repeat(1,1,
            max(1,math.ceil(height/embeddings.shape[-2])),
            max(1,math.ceil(width/embeddings.shape[-1])))[:, :, :height, :width]
    h,w=embeddings.shape[-2:]
    top,left=max((h-height)//2,0),max((w-width)//2,0)
    return [embeddings[:,:,top:top+height,left:left+width],
            embeddings[:,:,:height,:width], embeddings[:,:,-height:,:width],
            embeddings[:,:,-height:,-width:], embeddings[:,:,:height,-width:]]


class BFreeResearch(torch.nn.Module):
    def __init__(self,state):
        super().__init__()
        self.model=timm.create_model('vit_base_patch14_reg4_dinov2.lvd142m',
                                     num_classes=1,pretrained=False)
        self.model.set_input_size(img_size=504)
        self.model.load_state_dict(state,strict=True)
        self.patch_embed=self.model.patch_embed
        self.model.patch_embed=torch.nn.Identity()

    def forward(self,tensor):
        h,w=tensor.shape[-2:]
        if min(h,w)<14 or h*w>24_000_000:
            raise ValueError('Image outside bounded B-Free research dimensions')
        embeddings=self.patch_embed.proj(tensor)
        outputs=[]
        for crop in embedding_crops(embeddings,*self.patch_embed.grid_size):
            if self.patch_embed.flatten:
                crop=crop.flatten(2).transpose(1,2)
            outputs.append(self.model(self.patch_embed.norm(crop)))
        return torch.stack(outputs).mean(0)
