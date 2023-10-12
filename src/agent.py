import networkx as nx
import asyncio
import debugpy

from forta_agent import TransactionEvent
from sqlalchemy.future import select
from src.analysis.community_analysis.base_analyzer import (
    analyze_suspicious_clusters,
)

from analysis.transaction_analysis.algorithm import run_algorithm
from src.database.db_controller import get_async_session, initialize_database
from src.database.db_utils import (
    add_transaction_to_db,
    shed_oldest_Transfers,
    shed_oldest_ContractTransactions,
)
from src.database.models import Transfer
from src.graph.graph_controller import (
    add_transactions_to_graph,
    adjust_edge_weights_and_variances,
    convert_decimal_to_float,
    process_partitions,
    merge_new_communities,
)
from src.heuristics.initial_heuristics import apply_initial_heuristics
from src.utils import globals
from src.utils.constants import N
from src.utils.utils import update_transaction_counter
from src.database.clustering import write_graph_to_database

is_initial_batch = True
global_added_edges = []

debugpy.listen(5678)


def handle_transaction(transaction_event: TransactionEvent):
    initialize_database()
    return asyncio.get_event_loop().run_until_complete(
        handle_transaction_async(transaction_event)
    )


async def handle_transaction_async(transaction_event: TransactionEvent):
    findings = []

    print("applying initial heuristics")
    if not await apply_initial_heuristics(transaction_event):
        return []

    async with get_async_session() as session:
        try:
            await add_transaction_to_db(session, transaction_event)
            await session.commit()
            print("Transaction data committed to table")
        except Exception as e:
            print(f"Unexpected error occurred: {e}")
            session.rollback()

    update_transaction_counter()

    print("transaction counter is", globals.transaction_counter)
    if globals.transaction_counter >= N:
        print("processing clusters")
        findings.extend(await process_transactions())
        await shed_oldest_Transfers()
        await shed_oldest_ContractTransactions()

        globals.transaction_counter = 0
        print("ALL COMPLETE")
        return findings

    return []


previous_communities = {}


async def process_transactions():
    global is_initial_batch, previous_communities, global_added_edges
    findings = []
    debugpy.wait_for_client()
    async with get_async_session() as session:
        print("pulling all transfers...")
        result = await session.execute(
            select(Transfer).where(Transfer.processed == False).limit(N)
        )
        transfers = result.scalars().all()
        print("transfers pulled")
        print("Number of transfers:", len(transfers))

    # Create initial graph with all transfers
    added_edges = add_transactions_to_graph(transfers)
    print("added edges:", added_edges)
    global_added_edges.extend(added_edges)

    for transfer in transfers:
        transfer.processed = True
    await session.commit()

    # Set edge weights for graph
    adjust_edge_weights_and_variances(transfers)

    # Convert data from decimal to float for Louvain
    convert_decimal_to_float()

    # Generate subgraph from current batch of edges
    subgraph = globals.G1.edge_subgraph(global_added_edges)

    # Apply community detection on this subgraph
    subgraph_partitions = run_algorithm(subgraph)

    if not is_initial_batch:
        # Merge subgraph communities with the main graph
        subgraph_partitions = merge_new_communities(
            subgraph_partitions, previous_communities, global_added_edges, subgraph
        )
    else:
        # Set to False after the initial batch is processed
        is_initial_batch = False

    # Update the global graph with these partitions
    for node, community in subgraph_partitions.items():
        globals.G1.nodes[node]["community"] = community

    # Update previous_communities
    previous_communities.update(subgraph_partitions)

    process_partitions(subgraph_partitions)

    convert_decimal_to_float()

    nx.write_graphml(globals.G1, "G1_graph_output3.graphml")

    print("analyzing suspicious clusters")
    await analyze_suspicious_clusters() or []

    findings = await write_graph_to_database()

    # Reset global_added_edges for the next batch
    global_added_edges = []

    print("COMPLETE")
    return findings


# TODO: manage "cross-community edges"

# TODO: 1. don't replace any existing communities with louvain, just see if you have new communities
# TODO: 2. don't remove nodes / edges, until you are dropping old transactions, then just drop anything not part of a community
# TODO: 3. run LPA on existing communities to detect new nodes / edges

# TODO: label community centroids?
# TODO: have database retain the transactions and contract txs only for nodes in Sybil Clusters
# TODO: upgrade to Neo4j?

# TODO: double check advanced heuristics
# print("running advanced heuristics")
# await sybil_heuristics(globals.G1)

# TODO: status for active and inactive communities, alerts for new communities detected
# TODO: if new activity comes in on accounts already identified as sybils, flag it. monitor sybils specifically as new transactions come in

# TODO: does db need initialization?
