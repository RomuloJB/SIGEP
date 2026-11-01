from django.db import migrations, models


STATUS_CHOICES = [
    ("digitacao", "Em digitação"),
    ("pendente", "Pendente"),
    ("aprovado", "Aprovado"),
    ("rejeitado", "Rejeitado"),
    ("cancelado", "Cancelado"),
]


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0005_company_session_name"),
    ]

    operations = [
        # Os pedidos que já existem tiveram o estoque baixado na criação, por isso
        # entram como Pendente (status que mantém o estoque baixado) e aguardam o gerente.
        migrations.AddField(
            model_name="order",
            name="status",
            field=models.CharField(choices=STATUS_CHOICES, default="pendente", max_length=10, verbose_name="status"),
        ),
        # Pedidos novos começam em digitação
        migrations.AlterField(
            model_name="order",
            name="status",
            field=models.CharField(choices=STATUS_CHOICES, default="digitacao", max_length=10, verbose_name="status"),
        ),
    ]
