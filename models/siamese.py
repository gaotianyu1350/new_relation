import sys
import numpy as np
import random
sys.path.append('..')
import nrekit
import torch
from torch import autograd, optim, nn
from torch.autograd import Variable
from torch.nn import functional as F

class Siamese(nn.Module):

    def __init__(self, sentence_encoder, hidden_size=230):
        nn.Module.__init__(self)
        self.sentence_encoder = sentence_encoder # Should be different from main sentence encoder
        self.hidden_size = hidden_size
        self.fc = nn.Linear(hidden_size, 1)
        self.cost = nn.BCELoss(reduction="none")
        self._accuracy = 0.0

    def forward(self, data, num_size, num_class, threshold=0.5):
        x = self.sentence_encoder(data).contiguous().view(num_class, num_size, -1)
        x1 = x[:, :num_size/2].contiguous().view(-1, self.hidden_size)
        x2 = x[:, num_size/2:].contiguous().view(-1, self.hidden_size)
        y1 = x[:num_class/2].contiguous().view(-1, self.hidden_size)
        y2 = x[num_class/2:].contiguous().view(-1, self.hidden_size)
        label = torch.zeros((x1.size(0) + y1.size(0))).long().cuda()
        label[:x1.size(0)] = 1
        z1 = torch.cat([x1, y1], 0)
        z2 = torch.cat([x2, y2], 0)
        dis = torch.pow(z1 - z2, 2)
        score = F.sigmoid(self.fc(dis).squeeze())
        self._loss = self.cost(score, label.float()).mean()
        pred = torch.zeros((score.size(0))).long().cuda()
        pred[score > threshold] = 1
        self._accuracy = torch.mean((pred == label).type(torch.FloatTensor))
        self._prec = float(np.logical_and(pred == 1, label == 1).sum()) / float((pred == 1).sum() + 1)
        self._recall = float(np.logical_and(pred == 1, label == 1).sum()) / float((label == 1).sum() + 1)

    def forward_infer(self, x, y, threshold=0.5):
        x = self.sentence_encoder(x)
        support_size = x.size(0) / 2
        x = x[:support_size]
        y = self.sentence_encoder(y)
        x = x.unsqueeze(1)
        y = y.unsqueeze(0)
        dis = torch.pow(x - y, 2).view(-1, self.hidden_size)
        score = F.sigmoid(self.fc(dis).squeeze())
        pred = torch.zeros((score.size(0))).long().cuda()
        pred[score > threshold] = 1
        pred = pred.view(support_size, -1).sum(0)
        pred[pred >= 1] = 1
        return pred
    
class Snowball(nrekit.framework.Model):
    
    def __init__(self, sentence_encoder, base_class, siamese_model, hidden_size=230):
        nrekit.framework.Model.__init__(self, sentence_encoder)
        self.hidden_size = hidden_size
        self.base_class = base_class
        self.fc = nn.Linear(hidden_size, base_class)
        self.drop = nn.Dropout()
        self.siamese_model = siamese_model
        self.cost = nn.BCELoss(reduction='none')

    def forward_base(self, data):
        batch_size = data['word'].size(0)
        x = self.sentence_encoder(data) # (batch_size, hidden_size)
        x = self.drop(x)
        x = self.fc(x) # (batch_size, base_class)
        x = F.sigmoid(x)
        label = torch.zeros((batch_size, self.base_class)).cuda()
        label.scatter_(1, data['label'].view(-1, 1), 1) # (batch_size, base_class)
        loss_array = self.__loss__(x, label)
        self._loss = ((label.view(-1) + 1.0 / self.base_class) * loss_array).mean() * self.base_class
        _, pred = x.max(-1)
        self._accuracy = self.__accuracy__(pred, data['label'])

    def forward_new(self, data, threshold=0.5):
        support, query, unlabelled = data
        new_W = Variable(self.fc.weight.mean(0) / 1e3, requires_grad=True)
        new_bias = Variable(torch.zeros((1)), requires_grad=True)
        optimizer = optim.Adam([new_W, new_bias], 1e-1, weight_decay=0)
        new_W = new_W.cuda()
        new_bias = new_bias.cuda()

        # Expand
        support_x = self.sentence_encoder(support) # (batch_size, hidden_size)
        unlabelled_x = self.sentence_encoder(unlabelled)
        similar = self.siamese_model.forward_infer(support, unlabelled, threshold=0.95)
        chosen = []
        for i in range(similar.size(0)):
            if similar[i] == 1:
                chosen.append(unlabelled_x[i])
        self._snowball = similar.sum()
        if similar.sum() > 0:
            chosen = torch.stack(chosen, 0)
            chosen = torch.cat([support_x, chosen], 0)
            label = torch.cat([support['label'], torch.ones((chosen.size(0) - support['label'].size(0))).long().cuda()], 0)
        else:
            chosen = support_x
            label = support['label']

        '''
        for i in range(10):
            x = torch.matmul(support_x, new_W) + new_bias # (batch_size, 1)
            x = F.sigmoid(x)
            iter_loss_array = self.__loss__(x, support['label'].float())
            iter_loss = iter_loss_array.mean()
            iter_loss.backward(retain_graph=True)
            optimizer.step()
        '''

        for i in range(10):
            x = torch.matmul(chosen, new_W) + new_bias # (batch_size, 1)
            x = F.sigmoid(x)
            iter_loss_array = self.__loss__(x, label.float())
            iter_loss = iter_loss_array.mean()
            iter_loss.backward(retain_graph=True)
            optimizer.step()
        
        # Test
        query_x = self.sentence_encoder(query) # (batch_size, hidden_size)
        query_x = self.drop(query_x)
        x = torch.matmul(query_x, new_W) + new_bias # (batch_size, 1)
        x = F.sigmoid(x)
        loss_array = self.__loss__(x, query['label'].float())
        self._loss = loss_array.mean()
        pred = torch.zeros((x.size(0))).long().cuda()
        pred[x > threshold] = 1
        self._accuracy = self.__accuracy__(pred, query['label'])
        pred = pred.view(-1).data.cpu().numpy()
        label = query['label'].view(-1).data.cpu().numpy()
        self._prec = float(np.logical_and(pred == 1, label == 1).sum()) / float((pred == 1).sum() + 1)
        self._recall = float(np.logical_and(pred == 1, label == 1).sum()) / float((label == 1).sum() + 1)