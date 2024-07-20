from django.shortcuts import render
from django.http import JsonResponse
from pymongo import MongoClient
from bson.objectid import ObjectId
from collections import defaultdict, Counter
from django.http import HttpResponse

class TreeNode:
    def __init__(self, name, count, parent):
        self.name = name
        self.count = count
        self.node_link = None
        self.parent = parent
        self.children = {}

    def increment(self, count):
        self.count += count

def update_header(node, target):
    while node.node_link:
        node = node.node_link
    node.node_link = target

def update_tree(items, root, header, count):
    if items[0] in root.children:
        root.children[items[0]].increment(count)
    else:
        root.children[items[0]] = TreeNode(items[0], count, root)
        if header[items[0]][1] is None:
            header[items[0]][1] = root.children[items[0]]
        else:
            update_header(header[items[0]][1], root.children[items[0]])
    if len(items) > 1:
        update_tree(items[1:], root.children[items[0]], header, count)

def create_tree(transactions, min_support):
    header = defaultdict(int)
    for trans in transactions:
        for item in trans:
            header[item] += transactions[trans]
    header = {k: [v, None] for k, v in header.items() if v >= min_support}
    freq_items = set(header.keys())
    if not freq_items:
        return None, None
    root = TreeNode('Null', 1, None)
    for trans, count in transactions.items():
        local_items = [item for item in trans if item in freq_items]
        if local_items:
            local_items.sort(key=lambda x: header[x][0], reverse=True)
            update_tree(local_items, root, header, count)
    return root, header

def find_prefix_path(base_item, node):
    patterns = defaultdict(int)
    while node:
        prefix = []
        parent = node.parent
        while parent and parent.name != 'Null':
            prefix.append(parent.name)
            parent = parent.parent
        if prefix:
            patterns[tuple(prefix)] += node.count
        node = node.node_link
    return patterns

def mine_tree(header, min_support, prefix, freq_items):
    sorted_items = sorted(header.items(), key=lambda p: p[1][0])
    for item, [support, node] in sorted_items:
        new_prefix = prefix.copy()
        new_prefix.add(item)
        freq_items.append((new_prefix, support))
        cond_patterns = find_prefix_path(item, node)
        cond_tree, cond_header = create_tree(cond_patterns, min_support)
        if cond_header:
            mine_tree(cond_header, min_support, new_prefix, freq_items)

def generate_rules(freq_items, min_conf, transactions):
    rules = []
    for itemset, support in freq_items:
        if len(itemset) > 1:
            for item in itemset:
                antecedent = itemset - {item}
                confidence = support / sum(1 for trans in transactions if antecedent.issubset(trans))
                if confidence >= min_conf:
                    rules.append((antecedent, item, confidence))
    return rules

def recommend(rules, transaction):
    rec_counts = Counter()
    for antecedent, consequence, confidence in rules:
        if antecedent.issubset(transaction) and consequence not in transaction:
            rec_counts[consequence] += confidence
    return [item for item, _ in rec_counts.most_common()]

def recommendate(request):
    client = MongoClient("mongodb+srv://truongkhanhduydata:LljWL6XST4IhhRHB@cluster.qgnzikg.mongodb.net/Bookstore")
    db = client.Bookstore

    transactions = defaultdict(int)
    for order in db.orders.find():
        product_ids = tuple(str(product['productId']) for product in order.get('listOrder', []))
        transactions[product_ids] += 1

    search_query = request.GET.get('userId')
    if not search_query:
        return JsonResponse({"error": "userId is required"}, status=400)

    user_carts = db.carts.find_one({"userId": ObjectId(search_query)})
    if not user_carts:
        return JsonResponse({"error": "User cart not found"}, status=404)

    product_id_cart = [str(product['productId']) for product in user_carts['listItem']]

    min_support = 1
    min_conf = 0.4

    fp_tree, header_table = create_tree(transactions, min_support)
    freq_itemsets = []
    mine_tree(header_table, min_support, set(), freq_itemsets)

    rules = generate_rules(freq_itemsets, min_conf, transactions)

    new_transaction = set(product_id_cart)
    recommendations = recommend(rules, new_transaction)

    return JsonResponse({"userId": search_query, "productId": recommendations}, safe=False)