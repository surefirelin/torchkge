# -*- coding: utf-8 -*-
"""
Copyright TorchKGE developers
@author: Armand Boschin <aboschin@enst.fr>
"""

from torch import arange, matmul
from torch.nn import Module

from torchkge.utils import init_embedding, l1_dissimilarity, l2_dissimilarity
from torchkge.utils import get_rank, get_true_targets


class Model(Module):
    """Model interface to be used by any other class implementing a knowledge graph embedding model.

    Parameters
    ----------
    n_entities: int
        Number of entities to be embedded.
    n_relations: int
        Number of relations to be embedded.

    Attributes
    ----------
    n_ent: int
        Number of entities to be embedded.
    n_rel: int
        Number of relations to be embedded.

    """
    def __init__(self, n_entities, n_relations):
        super().__init__()
        self.n_ent = n_entities
        self.n_rel = n_relations

    def forward(self, heads, tails, negative_heads, negative_tails, relations):
        """Forward pass on the current batch.

        Parameters
        ----------
        heads: `torch.Tensor`, dtype: `torch.long`, shape: (batch_size)
            Integer keys of the current batch's heads
        tails: `torch.Tensor`, dtype: `torch.long`, shape: (batch_size)
            Integer keys of the current batch's tails.
        negative_heads: `torch.Tensor`, dtype: `torch.long`, shape: (batch_size)
            Integer keys of the current batch's negatively sampled heads.
        negative_tails: `torch.Tensor`, dtype: `torch.long`, shape: (batch_size)
            Integer keys of the current batch's negatively sampled tails.
        relations: `torch.Tensor`, dtype: `torch.long`, shape: (batch_size)
            Integer keys of the current batch's relations.

        Returns
        -------
        positive_triplets: `torch.Tensor`, dtype: `torch.float`, shape: (batch_size)
            Scoring function evaluated on true triples.
        negative_triplets: `torch.Tensor`, dtype: `torch.float`, shape: (batch_size)
            Scoring function evaluated on negatively sampled triples.

        """
        return self.scoring_function(heads, tails, relations), \
            self.scoring_function(negative_heads, negative_tails, relations)

    def scoring_function(self, h_idx, t_idx, r_idx):
        """Compute the scoring function for the triplets given as argument.

        Parameters
        ----------
        h_idx: `torch.Tensor`, dtype: `torch.long`, shape: (batch_size)
            Integer keys of the current batch's heads
        t_idx: `torch.Tensor`, dtype: `torch.long`, shape: (batch_size)
            Integer keys of the current batch's tails.
        r_idx: `torch.Tensor`, dtype: `torch.long`, shape: (batch_size)
            Integer keys of the current batch's relations.

        Returns
        -------
        score: `torch.Tensor`, dtype: `torch.float`, shape: (batch_size)
            Score function: opposite of dissimilarities between h+r and t.

        """
        raise NotImplementedError

    def normalize_parameters(self):
        raise NotImplementedError

    def evaluation_helper(self, h_idx, t_idx, r_idx):
        """Project current entities and candidates into relation-specific sub-spaces.

        Parameters
        ----------
        h_idx: `torch.Tensor`, shape: (b_size), dtype: `torch.long`
            Tensor containing indices of current head entities.
        t_idx: `torch.Tensor`, shape: (b_size), dtype: `torch.long`
            Tensor containing indices of current tail entities.
        r_idx: `torch.Tensor`, shape: (b_size), dtype: `torch.long`
            Tensor containing indices of current relations.

        Returns
        -------
        proj_h_emb: `torch.Tensor`, shape: (b_size, rel_emb_dim), dtype: `torch.float`
            Tensor containing embeddings of current head entities projected in relation space.
        proj_t_emb: `torch.Tensor`, shape: (b_size, rel_emb_dim), dtype: `torch.float`
            Tensor containing embeddings of current tail entities projected in relation space.
        proj_candidates: `torch.Tensor`, shape: (b_size, rel_emb_dim, n_entities), dtype: `torch.float`
            Tensor containing all entities projected in each relation spaces (relations
            corresponding to current batch's relations).
        r_emb: `torch.Tensor`, shape: (b_size, rel_emb_dim), dtype: `torch.float`
            Tensor containing current relations embeddings.

        """
        raise NotImplementedError

    def compute_ranks(self, proj_e_emb, proj_candidates, r_emb, e_idx, r_idx, true_idx, dictionary, heads=1):
        """Compute the ranks and the filtered ranks of true entities when doing link prediction. Note that the \
        best rank possible is 1.

        Parameters
        ----------
        proj_e_emb: `torch.Tensor`, shape: (batch_size, rel_emb_dim), dtype: `torch.float`
            Tensor containing current projected embeddings of entities.
        proj_candidates: `torch.Tensor`, shape: (b_size, rel_emb_dim, n_entities), dtype: `torch.float`
            Tensor containing projected embeddings of all entities.
        r_emb: `torch.Tensor`, shape: (batch_size, emb_dim), dtype: `torch.float`
            Tensor containing current embeddings of relations.
        e_idx: `torch.Tensor`, shape: (batch_size), dtype: `torch.long`
            Tensor containing the indices of entities.
        r_idx: `torch.Tensor`, shape: (batch_size), dtype: `torch.long`
            Tensor containing the indices of relations.
        true_idx: `torch.Tensor`, shape: (batch_size), dtype: `torch.long`
            Tensor containing the true entity for each sample.
        dictionary: default dict
            Dictionary of keys (int, int) and values list of ints giving all possible entities for
            the (entity, relation) pair.
        heads: integer
            1 ou -1 (must be 1 if entities are heads and -1 if entities are tails). \
            We test dissimilarity_type between heads * entities + relations and heads * targets.


        Returns
        -------
        rank_true_entities: `torch.Tensor`, shape: (b_size), dtype: `torch.int`
            Tensor containing the rank of the true entities when ranking any entity based on \
            computation of d(hear+relation, tail).
        filtered_rank_true_entities: `torch.Tensor`, shape: (b_size), dtype: `torch.int`
            Tensor containing the rank of the true entities when ranking only true false entities \
            based on computation of d(hear+relation, tail).

        """
        raise NotImplementedError

    def evaluate_candidates(self, h_idx, t_idx, r_idx, kg):
        """Compute the head and tail ranks and filtered ranks of the current batch.

        Parameters
        ----------
        h_idx: `torch.Tensor`, shape: (b_size), dtype: `torch.long`
            Tensor containing indices of current head entities.
        t_idx: `torch.Tensor`, shape: (b_size), dtype: `torch.long`
            Tensor containing indices of current tail entities.
        r_idx: `torch.Tensor`, shape: (b_size), dtype: `torch.long`
            Tensor containing indices of current relations.
        kg: `torchkge.data.KnowledgeGraph.KnowledgeGraph`
            Knowledge graph on which the model was trained.

        Returns
        -------
        rank_true_tails: `torch.Tensor`, shape: (b_size), dtype: `torch.int`
            Tensor containing the rank of the true tails when ranking any entity based on \
            computation of d(hear+relation, tail).
        filt_rank_true_tails: `torch.Tensor`, shape: (b_size), dtype: `torch.int`
            Tensor containing the rank of the true tails when ranking only true false entities \
            based on computation of d(hear+relation, tail).
        rank_true_heads: Tensor containing the rank of the true heads when ranking any entity based on \
            computation of d(hear+relation, tail).
        filt_rank_true_heads: `torch.Tensor`, shape: (b_size), dtype: `torch.int`
            Tensor containing the rank of the true heads when ranking only true false entities \
            based on computation of d(hear+relation, tail).

        """
        proj_h_emb, proj_t_emb, candidates, r_emb = self.evaluation_helper(h_idx, t_idx, r_idx)

        # evaluation_helper both ways (head, rel) -> tail and (rel, tail) -> head
        rank_true_tails, filt_rank_true_tails = self.compute_ranks(proj_h_emb,
                                                                   candidates,
                                                                   r_emb, h_idx, r_idx,
                                                                   t_idx,
                                                                   kg.dict_of_tails,
                                                                   heads=1)
        rank_true_heads, filt_rank_true_heads = self.compute_ranks(proj_t_emb,
                                                                   candidates,
                                                                   r_emb, t_idx, r_idx,
                                                                   h_idx,
                                                                   kg.dict_of_heads,
                                                                   heads=-1)

        return rank_true_tails, filt_rank_true_tails, rank_true_heads, filt_rank_true_heads


class TranslationModel(Model):
    """Model interface to be used by any other class implementing a translational knowledge graph embedding model.
    This interface inherits from the interface :class:`torchkge.models.interfaces.Model`.

    Parameters
    ----------
    ent_emb_dim: int
        Embedding dimension of the entities.
    n_entities: int
        Number of entities to be embedded.
    n_relations: int
        Number of relations to be embedded.
    dissimilarity_type: string
        Name of the dissimilarity function to be used.

    Attributes
    ----------
    entity_embeddings: `torch.nn.Embedding`
        Embedding object containing the embeddings of the entities.
    dissimilarity: function
        Dissimilarity function defined in `torchkge.utils.dissimilarities`.

    """
    def __init__(self, ent_emb_dim, n_entities, n_relations, dissimilarity_type):
        super().__init__(ent_emb_dim, n_entities, n_relations)

        self.entity_embeddings = init_embedding(self.n_ent, self.ent_emb_dim)

        assert dissimilarity_type in ['L1', 'L2', None]
        if dissimilarity_type == 'L1':
            self.dissimilarity = l1_dissimilarity
        elif dissimilarity_type == 'L2':
            self.dissimilarity = l2_dissimilarity
        else:
            self.dissimilarity = None

    def scoring_function(self, h_idx, t_idx, r_idx):
        raise NotImplementedError

    def normalize_parameters(self):
        raise NotImplementedError

    def evaluation_helper(self, h_idx, t_idx, r_idx):
        raise NotImplementedError

    def recover_project_normalize(self, ent_idx, rel_idx, normalize_):
        raise NotImplementedError

    def compute_ranks(self, proj_e_emb, proj_candidates, r_emb, e_idx, r_idx, true_idx, dictionary, heads=1):
        """Compute the ranks and the filtered ranks of true entities when doing link prediction. Note that the \
        best rank possible is 1.

        Parameters
        ----------
        proj_e_emb: `torch.Tensor`, shape: (batch_size, rel_emb_dim), dtype: `torch.float`
            Tensor containing current projected embeddings of entities.
        proj_candidates: `torch.Tensor`, shape: (b_size, rel_emb_dim, n_entities), dtype: `torch.float`
            Tensor containing projected embeddings of all entities.
        r_emb: `torch.Tensor`, shape: (batch_size, emb_dim), dtype: `torch.float`
            Tensor containing current embeddings of relations.
        e_idx: `torch.Tensor`, shape: (batch_size), dtype: `torch.long`
            Tensor containing the indices of entities.
        r_idx: `torch.Tensor`, shape: (batch_size), dtype: `torch.long`
            Tensor containing the indices of relations.
        true_idx: `torch.Tensor`, shape: (batch_size), dtype: `torch.long`
            Tensor containing the true entity for each sample.
        dictionary: default dict
            Dictionary of keys (int, int) and values list of ints giving all possible entities for
            the (entity, relation) pair.
        heads: integer
            1 ou -1 (must be 1 if entities are heads and -1 if entities are tails). \
            We test dissimilarity_type between heads * entities + relations and heads * targets.


        Returns
        -------
        rank_true_entities: `torch.Tensor`, shape: (b_size), dtype: `torch.int`
            Tensor containing the rank of the true entities when ranking any entity based on \
            computation of d(hear+relation, tail).
        filtered_rank_true_entities: `torch.Tensor`, shape: (b_size), dtype: `torch.int`
            Tensor containing the rank of the true entities when ranking only true false entities \
            based on computation of d(hear+relation, tail).

        """
        current_batch_size, embedding_dimension = proj_e_emb.shape

        # tmp_sum is either heads + r_emb or r_emb - tails (expand does not use extra memory)
        tmp_sum = (heads * proj_e_emb + r_emb).view((current_batch_size, embedding_dimension, 1))
        tmp_sum = tmp_sum.expand((current_batch_size, embedding_dimension, self.n_ent))

        # compute either dissimilarity_type(heads + relation, proj_candidates) or
        # dissimilarity_type(-proj_candidates, relation - tails)
        dissimilarities = self.dissimilarity(tmp_sum, heads * proj_candidates)

        # filter out the true negative samples by assigning infinite dissimilarity_type
        filt_dissimilarities = dissimilarities.clone()
        for i in range(current_batch_size):
            true_targets = get_true_targets(dictionary, e_idx, r_idx, true_idx, i)
            if true_targets is None:
                continue
            filt_dissimilarities[i][true_targets] = float('Inf')

        # from dissimilarities, extract the rank of the true entity.
        rank_true_entities = get_rank(-dissimilarities, true_idx)
        filtered_rank_true_entities = get_rank(-filt_dissimilarities, true_idx)

        return rank_true_entities, filtered_rank_true_entities

    def recover_candidates(self, h_idx, b_size):
        """Prepare candidates for link prediction evaluation.

        Parameters
        ----------
        h_idx: `torch.Tensor`, shape: (b_size), dtype: `torch.long`
            Tensor containing indices of current head entities.
        b_size: int
            Batch size.

        Returns
        -------
        candidates: `torch.Tensor`, shape: (b_size, emb_dim, number_entities), dtype: `torch.float`
            Tensor containing replications of all entities embeddings as many times as the batch size.

        """
        all_idx = arange(0, self.n_ent).long()
        if h_idx.is_cuda:
            all_idx = all_idx.cuda()
        candidates = self.entity_embeddings(all_idx).transpose(0, 1)
        candidates = candidates.view((1,
                                      self.ent_emb_dim,
                                      self.n_ent)).expand((b_size,
                                                           self.ent_emb_dim,
                                                           self.n_ent))
        return candidates

    @staticmethod
    def projection_helper(h_idx, t_idx, b_size, candidates, rel_emb_dim):
        mask = h_idx.view(b_size, 1, 1).expand(b_size, rel_emb_dim, 1)
        proj_h_emb = candidates.gather(dim=2, index=mask).view(b_size, rel_emb_dim)

        mask = t_idx.view(b_size, 1, 1).expand(b_size, rel_emb_dim, 1)
        proj_t_emb = candidates.gather(dim=2, index=mask).view(b_size, rel_emb_dim)

        return proj_h_emb, proj_t_emb


class BilinearModel(Model):

    def __init__(self, emb_dim, n_entities, n_relations):
        super().__init__(n_entities, n_relations)
        self.emb_dim = emb_dim

    def scoring_function(self, h_idx, t_idx, r_idx):
        raise NotImplementedError

    def normalize_parameters(self):
        raise NotImplementedError

    def evaluation_helper(self, h_idx, t_idx, r_idx):
        raise NotImplementedError

    @staticmethod
    def compute_product(h, t, r, emb_dim):
        """Compute the matrix product :math:`h^tRt` with proper reshapes. It can do the batch matrix
        product both in the forward pass and in the evaluation pass with one matrix containing
        all candidates.

        Parameters
        ----------
        h: `torch.Tensor`, shape: (b_size, emb_dim) or (b_size, self.n_ent, emb_dim), dtype: `torch.float`
            Tensor containing embeddings of current head entities or candidates.
        t: `torch.Tensor`, shape: (b_size, emb_dim) or (b_size, self.n_ent, emb_dim), dtype: `torch.float`
            Tensor containing embeddings of current tail entities or canditates.
        r: `torch.Tensor`, shape: (b_size, emb_dim, emb_dim), dtype: `torch.float`
            Tensor containing relation matrices for current relations.
        emb_dim: int
            Embedding dimension
        Returns
        -------
        product: `torch.Tensor`, shape: (b_size) or (b_size, self.n_ent), dtype: `torch.float`
            Tensor containing the matrix products :math:`h^t \\cdot R \\cdot t` for each sample of the batch.

        """
        b_size = h.shape[0]

        if len(h.shape) == 2 and len(t.shape) == 2:
            # this is the easy forward case
            return (matmul(h.view(b_size, 1, emb_dim), r).view(b_size, emb_dim) * t).sum(dim=1)

        elif len(h.shape) == 2 and len(t.shape) == 3:
            # this is the tail completion case in link prediction
            h = h.view(b_size, 1, emb_dim)
            return (matmul(h, r).view(b_size, emb_dim, 1) * t.transpose(1, 2)).sum(dim=1)
        else:
            # this is the head completion case in link prediction
            t = t.view(b_size, emb_dim, 1)
            return matmul(matmul(h, r), t).view(b_size, -1)

    def get_head_tail_candidates(self, h_idx, t_idx):
        b_size = h_idx.shape[0]

        candidates = self.ent_emb.weight.data
        candidates = candidates.view(1, self.n_ent, self.emb_dim)
        candidates = candidates.expand(b_size, self.n_ent, self.emb_dim)

        h_emb = self.ent_emb(h_idx)
        t_emb = self.ent_emb(t_idx)

        return h_emb, t_emb, candidates

    def compute_ranks(self, e_emb, candidates, r, e_idx, r_idx, true_idx, dictionary, heads=1):
        """Compute the ranks and the filtered ranks of true entities when doing link prediction.

        Parameters
        ----------
        e_emb: `torch.Tensor`, shape: (batch_size, rel_emb_dim), dtype: `torch.float`
            Tensor containing current embeddings of entities.
        candidates: torch tensor, shape: (b_size, number_entities, emb_dim), dtype: `torch.float`
            Tensor containing projected embeddings of all entities.
        r: `torch.Tensor`, shape: (b_size, emb_dim, emb_dim) or (b_size, emb_dim) dtype: `torch.float`
            Tensor containing current matrices or embeddings of relations.
        e_idx: torch tensor, shape: (batch_size), dtype: `torch.long`
            Tensor containing the indices of entities.
        r_idx: torch tensor, shape: (batch_size), dtype: `torch.long`
            Tensor containing the indices of relations.
        true_idx: torch tensor, shape: (batch_size), dtype: `torch.long`
            Tensor containing the true entity for each sample.
        dictionary: default dict
            Dictionary of keys (int, int) and values list of ints giving all possible entities for\
            the (entity, relation) pair.
        heads: integer
            1 ou -1 (must be 1 if entities are heads and -1 if entities are tails). We test\
             dissimilarity_type between heads * entities + relations and heads * targets.


        Returns
        -------
        rank_true_entities: torch Tensor, shape: (b_size), dtype: `torch.int`
            Tensor containing the rank of the true entities when ranking any entity based on\
            estimation of 1 or 0.
        filtered_rank_true_entities: torch Tensor, shape: (b_size), dtype: `torch.int`
            Tensor containing the rank of the true entities when ranking only true false entities\
            based on estimation of 1 or 0.

        """
        current_batch_size = r_idx.shape

        if heads == 1:
            scores = self.compute_product(e_emb, candidates, r, self.emb_dim)
        else:
            scores = self.compute_product(candidates, e_emb, r, self.emb_dim)

        # filter out the true negative samples by assigning negative score
        filt_scores = scores.clone()
        for i in range(current_batch_size):
            true_targets = get_true_targets(dictionary, e_idx, r_idx, true_idx, i)
            if true_targets is None:
                continue
            filt_scores[i][true_targets] = float(-1)

        # from dissimilarities, extract the rank of the true entity.
        rank_true_entities = get_rank(scores, true_idx)
        filtered_rank_true_entities = get_rank(filt_scores, true_idx)

        return rank_true_entities, filtered_rank_true_entities
