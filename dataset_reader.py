import tempfile
from typing import Dict, Iterable, List, Tuple

import torch

from allennlp.data import (
    DataLoader,
    DatasetReader,
    Instance,
    Vocabulary,
    TextFieldTensors,
)
from allennlp.data.data_loaders import SimpleDataLoader
from allennlp.data.fields import LabelField, TextField
from allennlp.data.token_indexers import TokenIndexer, SingleIdTokenIndexer
from allennlp.data.tokenizers import Token, Tokenizer, WhitespaceTokenizer
from allennlp.models import Model
from allennlp.modules import TextFieldEmbedder, Seq2VecEncoder
from allennlp.modules.text_field_embedders import BasicTextFieldEmbedder
from allennlp.modules.token_embedders import Embedding
from allennlp.modules.seq2vec_encoders import BagOfEmbeddingsEncoder
from allennlp.nn import util
from allennlp.training.metrics import CategoricalAccuracy
from allennlp.training.optimizers import AdamOptimizer
from allennlp.training.trainer import Trainer, GradientDescentTrainer
from allennlp.training.util import evaluate
from parameteres import Biencoder_params
import glob
import os
import random
import pdb
from tqdm import tqdm
import json

class BC5CDRReader(DatasetReader):
    def __init__(
        self,
        config,
        tokenizer: Tokenizer = None,
        token_indexers: Dict[str, TokenIndexer] = None,
        max_tokens: int = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.tokenizer = tokenizer or WhitespaceTokenizer()
        self.token_indexers = token_indexers or {"tokens": SingleIdTokenIndexer()}
        self.max_tokens = max_tokens
        self.config = config
        self.train_pmids, self.dev_pmids, self.test_pmids = self._train_dev_test_pmid_returner()
        self.id2mention, self.train_mention_ids, self.dev_mention_ids, self.test_mention_ids = \
            self._mention_id_returner(self.train_pmids, self.dev_pmids, self.test_pmids)

    def _read(self, train_dev_test_flag: str) -> Iterable[Instance]:
        '''
        :param train_dev_test_flag: 'train', 'dev', 'test'
        :return:
        '''

        mention_ids = list()
        if train_dev_test_flag == 'train':
            mention_ids += self.train_mention_id
            # Because original data is sorted with pmid documents, we have to shuffle data points for in-batch training.
            random.shuffle(mention_ids)
        elif train_dev_test_flag == 'dev':
            mention_ids += self.dev_mention_id
        elif train_dev_test_flag == 'test':
            mention_ids += self.test_mention_id

        # for idx, mention_uniq_id in tqdm(enumerate(mention_ids)):
        #     if mention_uniq_id in self.ignored_mention_idxs:
        #         continue
        #     data = self.one_line_parser(line=self.id2line[mention_uniq_id], mention_uniq_id=mention_uniq_id)
        #     yield self.text_to_instance(data=data)
        #
        # with open(file_path, "r") as lines:
        #     for line in lines:
        #         text, sentiment = line.strip().split("\t")
        #         tokens = self.tokenizer.tokenize(text)
        #         if self.max_tokens:
        #             tokens = tokens[: self.max_tokens]
        #         text_field = TextField(tokens, self.token_indexers)
        #         label_field = LabelField(sentiment)
        #         yield Instance({"text": text_field, "label": label_field})

    def _train_dev_test_pmid_returner(self):
        '''
        :return: pmids list for using and evaluating entity linking task
        '''
        train_pmids, dev_pmids, test_pmids = self._pmid_returner('train'), self._pmid_returner('dev'), \
                                             self._pmid_returner('test')
        train_pmids = [pmid for pmid in train_pmids if self._is_parsed_doc_exist_per_pmid(pmid)]
        dev_pmids = [pmid for pmid in dev_pmids if self._is_parsed_doc_exist_per_pmid(pmid)]
        test_pmids = [pmid for pmid in test_pmids if self._is_parsed_doc_exist_per_pmid(pmid)]

        return train_pmids, dev_pmids, test_pmids

    def _pmid_returner(self, train_dev_test_flag: str):
        '''
        :param train_dev_test_flag: train, dev, test
        :return: pmids (str list)
        '''
        assert train_dev_test_flag in ['train', 'dev', 'test']
        pmid_dir = self.config.dataset_dir
        pmids_txt_path = pmid_dir + 'corpus_pubtator_pmids_'
        if train_dev_test_flag == 'train':
            pmids_txt_path += 'trng'
        else:
            pmids_txt_path += train_dev_test_flag
        pmids_txt_path += '.txt'

        pmids = []
        with open(pmids_txt_path, 'r') as p:
            for line in p:
                line = line.strip()
                if line != '':
                    pmids.append(line)

        return pmids

    def _is_parsed_doc_exist_per_pmid(self, pmid: str):
        '''
        :param pmid:
        :return: if parsed doc exists in ./preprocessed_doc_dir/
        '''
        if os.path.exists(self.config.preprocessed_doc_dir + pmid + '.json'):
            return 1
        else:
            return 0

    def _mention_id_returner(self, train_pmids: list, dev_pmids: list, test_pmids: list):
        id2mention, train_mention_ids, dev_mention_ids, test_mention_ids = {}, [], [], []
        for pmid in train_pmids:
            mentions = self._pmid2mentions(pmid)
            for mention in mentions:
                id = len(id2mention)
                id2mention.update({id: mention})
                train_mention_ids.append(id)

        for pmid in dev_pmids:
            mentions = self._pmid2mentions(pmid)
            for mention in mentions:
                id = len(id2mention)
                id2mention.update({id: mention})
                dev_mention_ids.append(id)

        for pmid in test_pmids:
            mentions = self._pmid2mentions(pmid)
            for mention in mentions:
                id = len(id2mention)
                id2mention.update({id: mention})
                test_mention_ids.append(id)

        return id2mention, train_mention_ids, dev_mention_ids, test_mention_ids

    def _pmid2mentions(self, pmid):
        parsed_doc_json_path = self.config.preprocessed_doc_dir + pmid + '.json'
        with open(parsed_doc_json_path, 'r') as pd:
            parsed = json.load(pd)
        mentions = parsed['lines']

        return mentions

def build_dataset_reader(params) -> DatasetReader:
    return BC5CDRReader(params)

if __name__ == '__main__':
    config = Biencoder_params()
    params = config.opts
    build_dataset_reader(params)