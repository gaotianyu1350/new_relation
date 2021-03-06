import models
import nrekit
import sys
from torch import optim
from nrekit.data_loader_bert import JSONFileDataLoaderBERT as DataLoader

from pytorch_pretrained_bert import BertAdam

max_length = 90
train_data_loader = DataLoader('./data/train_train.json', vocab='./data/bert_vocab.txt', max_length=max_length)
val_data_loader = DataLoader('./data/train_val.json', vocab='./data/bert_vocab.txt', max_length=max_length, rel2id=train_data_loader.rel2id, shuffle=False)

framework = nrekit.framework.SuperviseFramework(train_data_loader, val_data_loader)
sentence_encoder = nrekit.sentence_encoder.BERTSentenceEncoder('./data/bert-base-uncased')
model = models.snowball.Siamese(sentence_encoder, hidden_size=768, drop_rate=0.1)

model_name = 'bert_siamese_euc_on_fewrel'

# set optimizer
batch_size = 32
train_iter = 30000

param_optimizer = list(model.named_parameters())
no_decay = ['bias', 'LayerNorm.bias', 'LayerNorm.weight']
optimizer_grouped_parameters = [
    {'params': [p for n, p in param_optimizer if not any(nd in n for nd in no_decay)], 'weight_decay': 0.01},
    {'params': [p for n, p in param_optimizer if any(nd in n for nd in no_decay)], 'weight_decay': 0.0}
    ]
optimizer = BertAdam(optimizer_grouped_parameters, lr=2e-5)

framework.train_siamese(model, model_name, optimizer=optimizer, batch_size=batch_size, train_iter=30000, learning_rate=2e-5, warmup=True)
