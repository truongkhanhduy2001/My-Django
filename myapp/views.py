# views.py
from django.shortcuts import render
from django.http import JsonResponse
from pymongo import MongoClient
from bson.objectid import ObjectId
from collections import defaultdict, Counter
from django.http import HttpResponse

# FP-Growth Implementation
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
    while node.node_link is not None:
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
    header = {}
    for trans in transactions:
        for item in trans:
            header[item] = header.get(item, 0) + transactions[trans]
    for item in list(header):
        if header[item] < min_support:
            del(header[item])
    freq_items = set(header.keys())
    if len(freq_items) == 0:
        return None, None
    for item in header:
        header[item] = [header[item], None]
    root = TreeNode('Null', 1, None)
    for trans, count in transactions.items():
        local_items = {}
        for item in trans:
            if item in freq_items:
                local_items[item] = header[item][0]
        if len(local_items) > 0:
            ordered_items = [v[0] for v in sorted(local_items.items(), key=lambda p: p[1], reverse=True)]
            update_tree(ordered_items, root, header, count)
    return root, header

def ascend_tree(node, path):
    if node.parent is not None:
        path.append(node.name)
        ascend_tree(node.parent, path)

def find_prefix_path(base_item, node):
    patterns = {}
    while node is not None:
        path = []
        ascend_tree(node, path)
        if len(path) > 1:
            patterns[tuple(path[1:])] = node.count
        node = node.node_link
    return patterns

def mine_tree(root, header, min_support, prefix, freq_items):
    sorted_items = [item[0] for item in sorted(header.items(), key=lambda p: p[1][0], reverse=True)]
    for base_item in sorted_items:
        new_prefix = prefix.copy()
        new_prefix.add(base_item)
        freq_items.append((new_prefix, header[base_item][0]))
        cond_patterns = find_prefix_path(base_item, header[base_item][1])
        cond_tree, cond_header = create_tree(cond_patterns, min_support)
        if cond_header is not None:
            mine_tree(cond_tree, cond_header, min_support, new_prefix, freq_items)

# Apriori and Association Rule Implementation
def generate_rules(freq_items, min_conf, transactions):
    rules = []
    for itemset, _ in freq_items:
        if len(itemset) > 1:
            for consequence in itemset:
                antecedent = itemset - {consequence}
                if antecedent:
                    support_antecedent = get_support(antecedent, transactions)
                    support_itemset = get_support(itemset, transactions)
                    confidence = support_itemset / support_antecedent
                    if confidence >= min_conf:
                        rules.append((antecedent, consequence, confidence))
    return rules

def get_support(itemset, transactions):
    support = 0
    for trans in transactions:
        if itemset.issubset(trans):
            support += 1
    return support / len(transactions)

# Recommendation System Implementation
def recommend(rules, transaction):
    rec_counts = Counter()
    for antecedent, consequence, confidence in rules:
        if antecedent.issubset(transaction) and consequence not in transaction:
            rec_counts[consequence] += 1
    sorted_recs = sorted(rec_counts, key=rec_counts.get, reverse=True)
    return sorted_recs

def index(request):
    return HttpResponse("Welcome to the Bookstore!")


transactions = []

def recommendate(request):
    # Kết nối đến MongoDB server
    client = MongoClient("mongodb+srv://truongkhanhduydata:LljWL6XST4IhhRHB@cluster.qgnzikg.mongodb.net/Bookstore")

    # Kết nối đến cơ sở dữ liệu
    db = client.Bookstore

    # Tạo một bộ sưu tập (Orders) tên là 'orders'
    Orders = db.orders

    for order in Orders.find():
        list_order = order.get('listOrder', [])
        product_id = [str(product['productId']) for product in list_order]
        transactions.append(product_id)
    
    # Lấy userId
    search_query = request.GET.get('userId')
    object_id = ObjectId(search_query)
    
    Carts = db.carts
    
    user_carts = Carts.find_one({"userId": object_id})
    
    product_id_cart = [str(product['productId']) for product in user_carts['listItem']]
    
    # Lấy id của sản phẩm
    Products = db.products
    
    product_object_id = [ObjectId(product) for product in product_id_cart]
    product_id_find = Products.find({"_id": {"$in": product_object_id}})
    product_id = list(product_id_find)
    
    # Prepare data for FP-Growth
    data_set = defaultdict(int)
    for trans in transactions:
        data_set[tuple(trans)] += 1

    # Minimum support and confidence
    min_support = 1
    min_conf = 0.4

    # Run FP-Growth
    fp_tree, header_table = create_tree(data_set, min_support)
    freq_itemsets = []
    mine_tree(fp_tree, header_table, min_support, set(), freq_itemsets)

    # Sort freq_itemsets by their count in descending order
    freq_itemsets = sorted(freq_itemsets, key=lambda x: x[1], reverse=True)

    # Generate association rules
    rules = generate_rules(freq_itemsets, min_conf, transactions)

    # Recommend based on a new transaction
    new_transaction = set(product_id_cart)
    recommendations = recommend(rules, new_transaction)

    return HttpResponse({"userId": search_query, "productId": recommendations}, safe=False)
