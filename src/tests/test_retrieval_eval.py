from evaluation.retrieval import hit_rate_and_mrr


class TestHitRateAndMrr:
    def test_all_hits_at_rank_one(self):
        results = [[1, 2, 3], [10, 20, 30]]
        true_ids = [1, 10]
        hit_rate, mrr = hit_rate_and_mrr(results, true_ids)
        assert hit_rate == 1.0
        assert mrr == 1.0

    def test_hit_at_lower_rank_reduces_mrr_not_hit_rate(self):
        results = [[1, 2, 3]]
        true_ids = [3]
        hit_rate, mrr = hit_rate_and_mrr(results, true_ids)
        assert hit_rate == 1.0
        assert mrr == 1 / 3

    def test_miss_scores_zero_for_both(self):
        results = [[1, 2, 3]]
        true_ids = [99]
        hit_rate, mrr = hit_rate_and_mrr(results, true_ids)
        assert hit_rate == 0.0
        assert mrr == 0.0

    def test_mixed_hits_and_misses_average_correctly(self):
        results = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        true_ids = [2, 99, 7]
        hit_rate, mrr = hit_rate_and_mrr(results, true_ids)
        assert hit_rate == 2 / 3
        assert mrr == (1 / 2 + 0 + 1) / 3
