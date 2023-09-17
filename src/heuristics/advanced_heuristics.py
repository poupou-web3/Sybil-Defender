from datetime import timedelta
from src.database.controller import SuspiciousCluster


async def sybil_heuristics(G, partitions, session):
    suspicious_clusters = []

    # Convert partitions to the new structure
    new_partitions = {}
    for node, cluster_id in partitions.items():
        if cluster_id not in new_partitions:
            new_partitions[cluster_id] = []
        new_partitions[cluster_id].append(node)

    print("checking nodes in partitions")

    for cluster_id, nodes in new_partitions.items():
        print("checking intra transactions")
        intra_transactions = sum(
            [G[u][v]["weight"] for u in nodes for v in nodes if v in G[u]]
        )
        print("checking inter transactions")
        inter_transactions = sum(
            [
                G[u][v]["weight"]
                for u in nodes
                for v in G
                if v not in nodes and v in G[u]
            ]
        )

        # Check intra/inter transaction ratio
        print("inter / intra transaction ratio check")
        if intra_transactions > (inter_transactions * 2):
            suspicious_clusters.append(cluster_id)
            continue  # No need to check other heuristics for this cluster, move to the next

        # TODO: set thresholds as environment variables
        for node in nodes:
            # Check transaction diversity
            print("running transaction diversity heuristic")
            diversity = transaction_diversity_heuristic(node, G)
            if diversity < 0.5:  # Define SOME_DIVERSITY_THRESHOLD
                print("diversity threshold met, adding to cluster")
                suspicious_clusters.append(cluster_id)
                break  # One suspicious node is enough to flag the cluster, move to the next cluster

            # Check account age
            print("checking account age heuristic")
            if account_age_heuristic(node, G):
                print("account age threshold met, adding to cluster")
                suspicious_clusters.append(cluster_id)
                break  # One suspicious node is enough to flag the cluster, move to the next cluster

    print("heuristic checks finished")

    # Once suspicious clusters are identified, we prune G and partitions
    nodes_to_retain = set()

    # Collect nodes associated with suspicious clusters
    for cluster_id in suspicious_clusters:
        nodes_to_retain.update(new_partitions[cluster_id])

    # Remove nodes from G that are not part of suspicious clusters
    for node in list(G.nodes()):  # Convert to list to avoid runtime modification errors
        if node not in nodes_to_retain:
            G.remove_node(node)

    # Remove nodes from partitions that are not part of suspicious clusters
    partitions = {
        node: cluster for node, cluster in partitions.items() if node in nodes_to_retain
    }
    await store_suspicious_clusters(suspicious_clusters, new_partitions, session)

    return G, partitions


async def store_suspicious_clusters(suspicious_clusters, new_partitions, session):
    # create an async session

    async with session.begin():
        for cluster_id in suspicious_clusters:
            for node in new_partitions[cluster_id]:
                new_entry = SuspiciousCluster(cluster_id, node)
                session.add(new_entry)

        # commit changes
        await session.commit()


def transaction_diversity_heuristic(node, G):
    neighbors = list(G.neighbors(node))
    total_weight = sum([G[node][neighbor]["weight"] for neighbor in neighbors])

    if total_weight == 0:
        return 0  # or some other default value

    return len(neighbors) / total_weight


def account_age_heuristic(node, G):  # Adjust parameters as needed
    # TODO: Fetch the account age
    age = None  # this needs to be defined

    transactions_count = len(list(G.neighbors(node)))
    if (
        age < timedelta(days=30) and transactions_count > 100
    ):  # Define SOME_THRESHOLD and ANOTHER_THRESHOLD
        return True
    return False
