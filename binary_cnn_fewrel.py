import models
import nrekit
import sys
import torch
from torch import optim
from nrekit.data_loader import JSONFileDataLoader as DataLoader
import argparse
import numpy as np

max_length = 40
train_train_data_loader = DataLoader('./data/train_train.json', './data/glove.6B.50d.json', max_length=max_length)
train_val_data_loader = DataLoader('./data/train_val.json', './data/glove.6B.50d.json', max_length=max_length)
val_data_loader = DataLoader('./data/val.json', './data/glove.6B.50d.json', max_length=max_length)
test_data_loader = DataLoader('./data/test.json', './data/glove.6B.50d.json', max_length=max_length)
distant = DataLoader('./data/distant.json', './data/glove.6B.50d.json', max_length=max_length, distant=True)

framework = nrekit.framework.Framework(train_val_data_loader, val_data_loader, test_data_loader, distant)
sentence_encoder = nrekit.sentence_encoder.CNNSentenceEncoder(train_val_data_loader.word_vec_mat, max_length)
sentence_encoder2 = nrekit.sentence_encoder.CNNSentenceEncoder(train_val_data_loader.word_vec_mat, max_length)

cnn_encoder_repre = torch.from_numpy(np.load('./_repre/cnn_encoder_on_fewrel.npy')).cuda()
cnn_siamese_repre = torch.from_numpy(np.load('./_repre/cnn_siamese_on_fewrel.npy')).cuda()
# cnn_encoder_repre = None
# cnn_siamese_repre = None

model2 = models.snowball.Siamese(sentence_encoder2, hidden_size=230, pre_rep=cnn_siamese_repre)
model = models.snowball.Snowball(sentence_encoder, base_class=train_val_data_loader.rel_tot, siamese_model=model2, hidden_size=230, neg_loader=train_train_data_loader, pre_rep=cnn_encoder_repre)

# load pretrain
checkpoint = torch.load('./checkpoint/cnn_encoder_on_fewrel.pth.tar.bak')['state_dict']
checkpoint2 = torch.load('./checkpoint/cnn_siamese_euc_on_fewrel.pth.tar.bak')['state_dict']
for key in checkpoint2:
    checkpoint['siamese_model.' + key] = checkpoint2[key]
model.load_state_dict(checkpoint)
model.cuda()
model.train()
model_name = 'cnn_snowball'

res = framework.eval(model, support_size=5, query_size=50)
res_file = open('exp_5shot.txt', 'a')
res_file.write(res + '\n')
