import models
import nrekit
import sys
from torch import optim
from nrekit.data_loader import JSONFileDataLoader
import torch

max_length = 40
train_data_loader = JSONFileDataLoader('./data/train_train.json', './data/glove.6B.50d.json', max_length=max_length)
val_data_loader = JSONFileDataLoader('./data/train_val.json', './data/glove.6B.50d.json', max_length=max_length)

framework = nrekit.framework.PretrainFramework(train_data_loader, val_data_loader)
sentence_encoder = nrekit.sentence_encoder.CNNSentenceEncoder(train_data_loader.word_vec_mat, max_length)
model = models.proto.Proto(sentence_encoder, base_class=train_data_loader.rel_tot, siamese_model=None, hidden_size=230)
model_name = 'proto_encoder'

# load pretrain
# checkpoint = torch.load('./checkpoint/cnn_encoder.pth.tar')['state_dict']
# own_state = model.state_dict()
# for name, param in checkpoint.items():
#     own_state[name].copy_(param)

framework.train_encoder(model, model_name, support=True, learning_rate=1)
