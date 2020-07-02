import os
import json
import argparse
import torch
import data_loader.data_loaders as module_data
# from data_loader.dataset import MAESTRO
from torch.utils.data import Dataset, DataLoader
import model.loss as module_loss
import model.metric as module_metric
import model.model as module_arch
from trainer import Trainer
from utils import Logger

# batch_size = 8 
# seq_len = 16000
# train_ds = MAESTRO(size=batch_size*, path='/data/MAESTRO', groups=['train'], sequence_length=seq_len)
# train_dl = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
# val_ds = MAESTRO(path='/data/MAESTRO', groups=['validation'], sequence_length=seq_len)
# val_dl = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)
# test_ds = MAESTRO(path='/data/MAESTRO', groups=['test'], sequence_length=seq_len)
# test_dl = DataLoader(test_ds, batch_size=batch_size, shuffle=False, num_workers=0)


def get_instance(module, name, config, *args):
    return getattr(module, config[name]['type'])(*args, **config[name]['args'])

def main(config, resume):
    #train_logger = Logger()

    # setup data_loader instances
    steps = config['trainer']['steps']
    data_loader = get_instance(module_data, 'data_loader', config, steps)
    valid_data_loader = data_loader.split_validation()

    # build model architecture
    model = get_instance(module_arch, 'arch', config)
    model.summary()

    # get function handles of loss and metrics
    #loss = getattr(module_loss, config['loss'])
    loss = get_instance(module_loss, 'loss', config)
    #metrics = [getattr(module_metric, met) for met in config['metrics']]

    # build optimizer, learning rate scheduler. delete every lines containing lr_scheduler for disabling scheduler
    trainable_params = filter(lambda p: p.requires_grad, model.parameters())
    optimizer = get_instance(torch.optim, 'optimizer', config, trainable_params)
    #lr_scheduler = get_instance(torch.optim.lr_scheduler, 'lr_scheduler', config, optimizer)

    trainer = Trainer(model, loss, optimizer,
                      resume=resume,
                      config=config,
                      data_loader=data_loader
                      #lr_scheduler=lr_scheduler
                      )

    trainer.train()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PyTorch WaveGlow')
    parser.add_argument('-c', '--config', default=None, type=str,
                           help='config file path (default: None)')
    parser.add_argument('-r', '--resume', default=None, type=str,
                           help='path to latest checkpoint (default: None)')
    parser.add_argument('-d', '--device', default=None, type=str,
                           help='indices of GPUs to enable (default: all)')
    args = parser.parse_args()

    if args.config:
        # load config file
        config = json.load(open(args.config))
        path = os.path.join(config['trainer']['save_dir'], config['name'])
    elif args.resume:
        # load config file from checkpoint, in case new config file is not given.
        # Use '--config' and '--resume' arguments together to load trained model and train more with changed config.
        config = torch.load(args.resume)['config']
    else:
        raise AssertionError("Configuration file need to be specified. Add '-c config.json', for example.")
    
    if args.device:
        os.environ["CUDA_VISIBLE_DEVICES"]=args.device

    main(config, args.resume)
