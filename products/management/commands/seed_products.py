"""
Django management command to seed InfiShelf with realistic CPG/FMCG products.
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from products.models import Product

SEED_PRODUCTS = [
    # Category 1: Beverages & Energy Drinks
    {
        "name": "Coca-Cola Zero Sugar Cans (Pack of 12)",
        "brand": "Coca-Cola",
        "category": "Beverages & Energy Drinks",
        "description": "Crisp, delicious, refreshing taste of Coca-Cola without the sugar and zero calories. Perfect for sharing with friends and family during gatherings.",
        "price": Decimal("449.00"),
        "image_url": "/products/coca-cola-zero.jpg",
        "tags": ["zero-sugar", "soda", "coke", "refreshment", "beverage", "pack-of-12"]
    },
    {
        "name": "Monster Energy Ultra White 500ml",
        "brand": "Monster Energy",
        "category": "Beverages & Energy Drinks",
        "description": "Lighter tasting, less sweet, sparkling citrus energy drink with zero calories and zero sugar, packed with Monster's signature energy blend.",
        "price": Decimal("125.00"),
        "image_url": "/products/monster-energy-ultra.jpg",
        "tags": ["energy-drink", "zero-sugar", "citrus", "ultra-white", "caffeine"]
    },
    {
        "name": "Red Bull Sugarfree Energy Drink 250ml",
        "brand": "Red Bull",
        "category": "Beverages & Energy Drinks",
        "description": "Red Bull Sugarfree gives you wings without sugar. Formulated with high-quality ingredients including caffeine, taurine, B-group vitamins, and alpine water.",
        "price": Decimal("125.00"),
        "image_url": "/products/red-bull-sugarfree.jpg",
        "tags": ["energy-drink", "sugarfree", "wings", "focus", "vitality"]
    },
    {
        "name": "Tropicana 100% Pure Premium Orange Juice 1.5L",
        "brand": "Tropicana",
        "category": "Beverages & Energy Drinks",
        "description": "Never from concentrate, 100% pure squeezed Florida orange juice with no added sugar, artificial flavors, or preservatives. Rich in Vitamin C.",
        "price": Decimal("165.00"),
        "image_url": "/products/tropicana-orange-juice.jpg",
        "tags": ["orange-juice", "vitamin-c", "pure-juice", "breakfast", "natural"]
    },

    # Category 2: Snacks & Confectionery
    {
        "name": "Doritos Nacho Cheese Tortilla Chips 200g",
        "brand": "Frito-Lay",
        "category": "Snacks & Confectionery",
        "description": "Bold, iconic nacho cheese flavor packed into tooth-rattling crunchy triangular tortilla chips. The quintessential snack for game nights and movie marathons.",
        "price": Decimal("90.00"),
        "image_url": "/products/doritos-nacho-cheese.jpg",
        "tags": ["nacho-cheese", "tortilla-chips", "crunchy", "party-snack", "frito-lay"]
    },
    {
        "name": "Lay's Classic Salted Potato Chips Family Pack",
        "brand": "Lay's",
        "category": "Snacks & Confectionery",
        "description": "Crispy golden potato chips cooked to perfection with just the right touch of sea salt. Made from specially selected farm-grown potatoes.",
        "price": Decimal("45.00"),
        "image_url": "/products/lays-classic-salted.jpg",
        "tags": ["potato-chips", "salted", "classic", "family-pack", "crispy"]
    },
    {
        "name": "Oreo Double Stuf Chocolate Sandwich Cookies 400g",
        "brand": "Mondelēz",
        "category": "Snacks & Confectionery",
        "description": "Twist, lick, and dunk! Stuffed with twice the delicious signature sweet crème between two embossed chocolate wafer cookies.",
        "price": Decimal("120.00"),
        "image_url": "/products/oreo-double-stuf.jpg",
        "tags": ["cookies", "chocolate", "double-stuf", "sweet", "biscuits"]
    },
    {
        "name": "Kinder Bueno Crispy Hazelnut Bar (4-Pack)",
        "brand": "Ferrero",
        "category": "Snacks & Confectionery",
        "description": "Delicate crispy wafer filled with luscious hazelnut cream, enrobed in smooth milk chocolate and drizzled with dark chocolate stripe.",
        "price": Decimal("199.00"),
        "image_url": "/products/kinder-bueno.jpg",
        "tags": ["chocolate-bar", "hazelnut", "wafer", "confectionery", "treat"]
    },

    # Category 3: Personal Care & Grooming
    {
        "name": "Dove Deep Moisture Hydrating Body Wash 650ml",
        "brand": "Unilever",
        "category": "Personal Care & Grooming",
        "description": "Nourishing body wash formulated with NutriumMoisture technology that penetrates deep into surface layers of skin for instant softness and lasting smoothness.",
        "price": Decimal("425.00"),
        "image_url": "/products/dove-body-wash.jpg",
        "tags": ["body-wash", "dove", "hydrating", "skincare", "moisturizer"]
    },
    {
        "name": "Nivea Men Sensitive Post Shave Balm 100ml",
        "brand": "Nivea",
        "category": "Personal Care & Grooming",
        "description": "Alcohol-free soothing post-shave balm enriched with chamomile and vitamin E to immediately calm irritated skin and alleviate redness.",
        "price": Decimal("299.00"),
        "image_url": "/products/nivea-post-shave-balm.jpg",
        "tags": ["shave-balm", "grooming", "sensitive-skin", "chamomile", "mens-care"]
    },
    {
        "name": "Colgate Total Whitening Toothpaste 120g",
        "brand": "Colgate",
        "category": "Personal Care & Grooming",
        "description": "12-hour antibacterial protection for whole mouth health. Fights plaque, gingivitis, tartar, and surface stains for a brighter, healthier smile.",
        "price": Decimal("145.00"),
        "image_url": "/products/colgate-total-toothpaste.jpg",
        "tags": ["toothpaste", "oral-care", "whitening", "antibacterial", "fresh-breath"]
    },
    {
        "name": "Head & Shoulders Classic Clean Anti-Dandruff Shampoo 400ml",
        "brand": "P&G",
        "category": "Personal Care & Grooming",
        "description": "Clinically proven to provide up to 100% flake-free scalp protection. pH balanced formula gentle enough for daily hair washing.",
        "price": Decimal("375.00"),
        "image_url": "/products/head-and-shoulders-shampoo.jpg",
        "tags": ["shampoo", "anti-dandruff", "hair-care", "classic-clean", "scalp-care"]
    },

    # Category 4: Home & Fabric Care
    {
        "name": "Ariel Matic Front Load Liquid Detergent 2L",
        "brand": "P&G",
        "category": "Home & Fabric Care",
        "description": "Cutting-edge enzymatic liquid detergent engineered specifically for fully automatic front-load washing machines. Removes tough stains in 1 wash.",
        "price": Decimal("450.00"),
        "image_url": "/products/ariel-liquid-detergent.jpg",
        "tags": ["detergent", "laundry", "stain-removal", "fabric-care", "ariel"]
    },
    {
        "name": "Dettol Multi-Surface Disinfectant Liquid 1L",
        "brand": "Reckitt",
        "category": "Home & Fabric Care",
        "description": "Hospital-grade surface disinfectant proven to kill 99.9% of bacteria and viruses. Suitable for floors, kitchen counters, and bathroom tiles.",
        "price": Decimal("215.00"),
        "image_url": "/products/dettol-disinfectant.jpg",
        "tags": ["disinfectant", "cleaning", "sanitizer", "surface-cleaner", "germ-protection"]
    },
    {
        "name": "Vim Ultra Power Lemon Dishwash Gel 750ml",
        "brand": "Unilever",
        "category": "Home & Fabric Care",
        "description": "Concentrated degreasing formula infused with real lemon juice. Powers through burnt grease on pots, pans, and glassware leaving a sparkling shine.",
        "price": Decimal("155.00"),
        "image_url": "/products/vim-dishwash-gel.jpg",
        "tags": ["dishwash", "kitchen-cleaning", "lemon-fresh", "grease-removal"]
    },

    # Category 5: Dairy & Breakfast
    {
        "name": "Nestlé Koko Krunch Choco Cereal 375g",
        "brand": "Nestlé",
        "category": "Dairy & Breakfast",
        "description": "Crispy whole grain chocolate cereal curls enriched with essential vitamins, iron, and calcium. Turns the morning milk delightfully chocolaty.",
        "price": Decimal("220.00"),
        "image_url": "/products/nestle-koko-krunch.jpg",
        "tags": ["cereal", "breakfast", "chocolate", "whole-grain", "kids-breakfast"]
    },
    {
        "name": "Chobani Greek Yogurt Mixed Berry 150g",
        "brand": "Chobani",
        "category": "Dairy & Breakfast",
        "description": "Triple strained authentic Greek yogurt layered over real ripe blackberries, blueberries, and raspberries. High protein with zero artificial flavors.",
        "price": Decimal("65.00"),
        "image_url": "/products/chobani-greek-yogurt.jpg",
        "tags": ["greek-yogurt", "protein", "mixed-berry", "probiotics", "dairy"]
    },
    {
        "name": "Nutella Hazelnut Spread with Cocoa 750g",
        "brand": "Ferrero",
        "category": "Dairy & Breakfast",
        "description": "The world's favorite hazelnut cocoa spread made from sustainably sourced ingredients. Irresistibly smooth spread for toast, pancakes, and fruit.",
        "price": Decimal("699.00"),
        "image_url": "/products/nutella-hazelnut-spread.jpg",
        "tags": ["hazelnut-spread", "nutella", "cocoa", "breakfast", "sweet-spread"]
    },
]

class Command(BaseCommand):
    help = "Seeds initial CPG/FMCG products into InfiShelf catalog."

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all existing products before seeding.',
        )

    def handle(self, *args, **options):
        if options['clear']:
            deleted_count, _ = Product.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Cleared {deleted_count} existing products."))

        # Get or create default admin/system user to associate with initial products
        admin_user, _ = User.objects.get_or_create(
            username='system_admin',
            defaults={
                'email': 'admin@infishelf.com',
                'is_staff': True,
                'is_superuser': True
            }
        )

        created_count = 0
        skipped_count = 0

        for item in SEED_PRODUCTS:
            if Product.objects.filter(name=item["name"], brand=item["brand"]).exists():
                skipped_count += 1
                continue

            Product.objects.create(
                name=item["name"],
                brand=item["brand"],
                category=item["category"],
                description=item["description"],
                price=item["price"],
                image_url=item["image_url"],
                tags=item["tags"],
                created_by=admin_user
            )
            created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seeding completed successfully! Created: {created_count}, Skipped (already exist): {skipped_count}."
        ))
