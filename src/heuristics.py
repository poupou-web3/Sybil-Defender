def sybil_heuristics(G, partitions):
    suspicious_clusters = []

    for cluster, nodes in partitions.items():
        intra_transactions = sum(
            [G[u][v]["weight"] for u in nodes for v in nodes if v in G[u]]
        )
        inter_transactions = sum(
            [
                G[u][v]["weight"]
                for u in nodes
                for v in G
                if v not in nodes and v in G[u]
            ]
        )

        if intra_transactions > (
            inter_transactions * 2
        ):  # Adjust the ratio based on your needs
            suspicious_clusters.append(cluster)

    return suspicious_clusters


def transaction_diversity_heuristic(node, G):
    neighbors = list(G.neighbors(node))
    return len(neighbors) / sum([G[node][neighbor]["weight"] for neighbor in neighbors])


def account_age_heuristic(
    node, transaction_event
):  # Needs more info about how account age is determined
    # TODO: Fetch the account age
    age = None  # this needs to be defined

    transactions_count = len(list(G.neighbors(node)))
    if age < SOME_THRESHOLD and transactions_count > ANOTHER_THRESHOLD:
        return True
    return False


# After clustering
suspicious_clusters = sybil_heuristics(G, partitions)

for cluster in suspicious_clusters:
    for node in cluster:
        diversity = transaction_diversity_heuristic(node, G)
        if diversity < SOME_DIVERSITY_THRESHOLD:
            print(f"Node {node} has suspicious transaction diversity.")

        if account_age_heuristic(node, transaction_event):
            print(
                f"Node {node} has suspicious account age to transaction frequency ratio."
            )
