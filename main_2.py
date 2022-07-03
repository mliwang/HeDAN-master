import torch
import torch.nn.functional as F
from sklearn.metrics import f1_score
import numpy as np
from utils import EarlyStopping
from builtins import str
from models import HeDAN
from DataPreprocess import MakeGlobalGraph, DataConstruct, DATA_DIR, OUT_DIR





def evaluate(model, g, features, data, loss_fcn, epoch):
    model.eval()
    total_loss = 0
    total_error = 0
    count = 0
    with torch.no_grad():
        for i, batch in enumerate(
                data):  # tqdm(training_data, mininterval=2, desc='  - (Training)   ', leave=False):
            # prepare data
            tgt, tgt_timestamp, tgt_label, tgt_index = (item.cuda() for item in batch)
            z, pred = model(tgt, tgt_timestamp, tgt_index, g, features)
            #pred = torch.exp(pred).to(torch.float32)
            loss = loss_fcn(pred.to(torch.float32), tgt_label.to(torch.float32))
            error = torch.median(
                torch.square((pred.to(torch.float32) - tgt_label.to(torch.float32)) ))
            total_loss += loss
            total_error += error
            count += 1
            if i % 100 == 0:
                print('Epoch {:d} | Batch {:d} | Vaild Loss {:.4f} | Vaild Error {:.4f} '.format(
                    epoch + 1, i + 1, loss.item(), error.item()))

    return loss, error

def main(args):
    g = MakeGlobalGraph()
    print(g)
    print("User node amount: {}".format(g.number_of_nodes("user")))
    print("Message node amount: {}".format(g.number_of_nodes("message")))
    print("Friendship edge amount: {}".format(g.number_of_edges("follow")))
    print("Interest edge amount: {}".format(g.number_of_edges("interest")))
    print("Interaction edge amount: {}".format(g.number_of_edges("retweet")))

    #batch_size = 10000
    train_data = DataConstruct(DATA_DIR, data=0, load_dict=True, batch_size=args['batch_size'], cuda=False, interval = args['interval'], data_name = args['data_name'])
    valid_data = DataConstruct(DATA_DIR, data=1, batch_size=args['batch_size'], cuda=False, interval = args['interval'], data_name = args['data_name'])  # torch.cuda.is_available()
    test_data = DataConstruct(DATA_DIR, data=2, batch_size=args['batch_size'], cuda=False, interval = args['interval'], data_name = args['data_name'])
    #print("All cascade size : {}".format(train_data.all_size))
    print("Train cascade size : {}".format(train_data.train_size))
    print("Valid cascade size : {}".format(train_data.valid_size))
    print("Test cascade size : {}".format(train_data.test_size))



    features_m = torch.randn(g.number_of_nodes('message'), 1000)
    features_u = torch.randn(g.number_of_nodes('user'), 10000)

    features_m = features_m.to(args['device'])
    features_u = features_u.to(args['device'])

    features = {'message': features_m, 'user': features_u}
    
    in_size = {'message': features_m.shape[1], 'user': features_u.shape[1]}


    model = HeDAN(meta_paths=[['follow'],['retweet'],['interest']],
                 in_size=in_size,
                 hidden_size=args['hidden_units'],
                 out_size=args['out_size'],
                 aggre_type='attention',
                 num_heads=args['num_heads'],
                 dropout=args['dropout'])


    model.to(args['device'])
    g = g.to(args['device'])

    stopper = EarlyStopping(patience=args['patience'])
    loss_fcn = torch.nn.MSELoss(reduction='mean')
    optimizer = torch.optim.Adam(model.parameters(), lr=args['lr'],
                                 weight_decay=args['weight_decay'])



    for epoch in range(args['num_epochs']):
        model.train()

        print("--------------------Epoch {:d}----------------------".format(epoch+1))

        for i, batch in enumerate(
                train_data):  # tqdm(training_data, mininterval=2, desc='  - (Training)   ', leave=False):
            # prepare data
            tgt, tgt_timestamp, tgt_label, tgt_index = (item.cuda() for item in batch)
            z , pred  = model(tgt, tgt_timestamp, tgt_index, g, features)

            loss = loss_fcn(pred.to(torch.float32), tgt_label.to(torch.float32))
            error = torch.median(torch.square((pred.to(torch.float32) - tgt_label.to(torch.float32))))
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            if i%100 == 0:
                print('Epoch {:d} | Batch {:d} | Train Loss {:.4f} | Train Error {:.4f}'.format(
                    epoch + 1, i + 1, loss.item(), error.item()))

        
        val_loss, val_error = evaluate(model, g, features, valid_data, loss_fcn, epoch)
        early_stop = stopper.step(val_loss.data.item(), val_error.data.item(),model)


        if early_stop:
            break

    stopper.load_checkpoint(model)
    test_loss, test_error = evaluate(model, g, features, test_data, loss_fcn, 1)

    print('Test loss {:.4f} | Test Error {:.4f}'.format(
        test_loss.item(), test_error.item()))






if __name__ == '__main__':
    import argparse
    from utils import setup
    parser = argparse.ArgumentParser('HeDAN')
    print(parser)
    parser.add_argument('-s', '--seed', type=int, default=1,
                        help='Random seed')
    parser.add_argument('-ld', '--log-dir', type=str, default='results',
                        help='Dir for saving training results')
    args = parser.parse_args().__dict__
    args = setup(args)
    print(args)
    main(args)