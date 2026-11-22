"""분류 모델 불러오기 · 예측 (담당: 모델).

modeling/weights/best.pt(git 제외)와 modeling/classes.txt(Food-101 meta 순서)를 쓴다. 두 종류를 모두 읽는다:
- timm 체크포인트 {'model','epoch','val_top1','cfg'} — 주한솔 hansol_train_convnext.ipynb
  (`convnext_base.fb_in22k_ft_in1k`, EMA 가중치). 앱 기본 = exp004 (12에폭 최고, test top-1 93.46%)
- torchvision state_dict — 처음 학습한 ConvNeXt-Tiny. test top-1 88.8%
모델 크기(tiny/small/base/large)는 가중치 모양으로 알아낸다 (김유라).
전처리는 학습 때와 같게: timm은 bicubic, torchvision은 bilinear (짧은 변 256 → 가운데 224, 크기는 cfg를 따름).
확률 보정값(temperature)은 modeling/calibration.json (notebooks/05 결과). 그 파일의 model이 불러온 모델과 같을 때만 쓴다.
"""
import json
from pathlib import Path

import torch
import torch.nn as nn
from torchvision import models, transforms as T

HERE = Path(__file__).parent
WEIGHTS = HERE / 'weights' / 'best.pt'
CALIB = HERE / 'calibration.json'
SIZES = {(96, 9): 'convnext_tiny', (96, 27): 'convnext_small', (128, 27): 'convnext_base', (192, 27): 'convnext_large'}


def _tf(size=224, bicubic=False):
    mode = T.InterpolationMode.BICUBIC if bicubic else T.InterpolationMode.BILINEAR
    return T.Compose([T.Resize(int(size * 256 / 224), interpolation=mode), T.CenterCrop(size), T.ToTensor(),
                      T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])


TF = _tf()   # 처음 Tiny 전처리 (예전 노트북 호환용)


def _arch(sd, timm_keys):
    """가중치 모양으로 tiny/small/base/large를 알아낸다 (첫 층 채널 수, 3번째 단계 블록 수)."""
    first, stage = ('stem.0.weight', 'stages.2.blocks.') if timm_keys else ('features.0.0.weight', 'features.5.')
    depth = len({k[len(stage):].split('.')[0] for k in sd if k.startswith(stage)})
    return SIZES[(sd[first].shape[0], depth)]


def load_model(weights=WEIGHTS, classes=HERE / 'classes.txt'):
    """→ (모델, 클래스 목록). 모델에 .kind(예: convnext_base), .preprocess, .temperature를 붙여 둔다."""
    classes = Path(classes).read_text(encoding='utf-8').split()
    ckpt = torch.load(weights, map_location='cpu', weights_only=False)  # 팀이 만든 파일만 넣을 것
    wrapped = isinstance(ckpt, dict) and 'model' in ckpt
    cfg = (ckpt.get('cfg') or {}) if wrapped else {}
    sd = ckpt['model'] if wrapped else ckpt
    sd = {k.removeprefix('_orig_mod.').removeprefix('module.'): v for k, v in sd.items()}  # compile/DataParallel 접두어
    timm_keys = 'stem.0.weight' in sd
    name = _arch(sd, timm_keys)
    if timm_keys:
        import timm
        m = timm.create_model(name, pretrained=False, num_classes=len(classes))
    else:
        m = getattr(models, name)()
        m.classifier[-1] = nn.Linear(m.classifier[-1].in_features, len(classes))
    m.load_state_dict(sd)
    size = next((cfg[k] for k in ('img_size', 'image_size', 'input_size') if isinstance(cfg.get(k), int)), 224)
    m.kind, m.preprocess = name, _tf(size, bicubic=timm_keys)
    cal = json.loads(CALIB.read_text(encoding='utf-8')) if CALIB.exists() else {}
    m.temperature = cal['temperature'] if cal.get('model') == m.kind else 1.0
    return m.eval(), classes


@torch.no_grad()
def predict(model, img, k=3):
    """PIL 이미지 → [(클래스, 확률)] 상위 k개. 확률은 temperature로 보정된 값 (judge의 T_ONE·T_KNOWN도 보정 기준)."""
    m, classes = model
    conf, idx = (m(m.preprocess(img.convert('RGB'))[None]) / m.temperature).softmax(1)[0].topk(k)
    return [(classes[i], float(c)) for c, i in zip(conf, idx)]
