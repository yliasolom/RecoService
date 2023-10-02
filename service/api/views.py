from typing import List
import dill
import pandas as pd
import yaml

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from service.api.exceptions import (
    ModelNotFoundError,
    NotAuthorizedError,
    UserNotFoundError,
)
from service.api.responses import responses
from service.log import app_logger

with open('config/config.yaml') as f:
    config = yaml.safe_load(f)


class RecoResponse(BaseModel):
    user_id: int
    items: List[int]


router = APIRouter()
bearer_http = HTTPBearer()

userknn_recos_off = pd.read_csv(config['userknn_model']['offline'])
popular_recos_off = list(
    pd.read_csv(config['popular_model']['offline']).item_id)


@router.get(
    path="/health",
    tags=["Health"],
)
async def health() -> str:
    return "I am alive - 36.6"


@router.get(
    path="/reco/{model_name}/{user_id}",
    tags=["Recommendations"],
    response_model=RecoResponse,
    responses=responses,
)
async def get_reco(
    request: Request,
    model_name: str,
    user_id: int,
    token: HTTPAuthorizationCredentials = Depends(bearer_http)
) -> RecoResponse:
    app_logger.info(f"Request for model: {model_name}, user_id: {user_id}")

    # Write your code here
    if token.credentials != config['Service']['token']:
        raise NotAuthorizedError(error_message=f"Token {user_id} bad")
    elif model_name not in config['Service']['models']:
        raise ModelNotFoundError(error_message=f"Model name {model_name} bad")
    elif user_id > 10 ** 9:
        raise UserNotFoundError(error_message=f"User {user_id} not found")

    k_recs = request.app.state.k_recs
    if model_name == 'test_model':
        reco = list(range(config['test_model']['n_recs']))

    elif model_name == 'userknn_model':
        if config['userknn_model']['online_mode']:
            with open(config['userknn_model']['online'], 'rb') as f:
                model = dill.load(f)
            userknn_recos = model.predict_online(user_id, k_recs)

            with open(config['popular_model']['online'], 'rb') as f:
                model = dill.load(f)
            popular_recos = model.predict_online(user_id, k_recs)

            if len(userknn_recos) == k_recs:
                reco = reco[reco.score > 3]
            i = 0
            reco = list(reco.item_id)
            while len(reco) < k_recs:
                if popular_recos[i] not in reco:
                    reco.append(popular_recos[i])
                i += 1
        else:
            reco = userknn_recos_off[userknn_recos_off['user_id'] == user_id]
            if len(reco) == 0:
                reco = []
            elif len(reco) <= k_recs:
                reco = reco[reco.score > 2.5]
                reco = list(reco.item_id)
            i = 0
            while len(reco) < k_recs:
                if popular_recos_off[i] not in reco:
                    reco.append(popular_recos_off[i])
                i += 1

    return RecoResponse(user_id=user_id, items=reco)


def add_views(app: FastAPI) -> None:
    app.include_router(router)
