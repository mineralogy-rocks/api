# -*- coding: UTF-8 -*-
from itertools import chain

from django.contrib.humanize.templatetags.humanize import naturalday
from django.contrib.postgres.aggregates import ArrayAgg
from django.db import connection
from django.db import models
from django.db.models import F
from django.db.models import Prefetch
from rest_framework import serializers

from ..annotations import _annotate__statuses_array
from ..choices import INHERIT_CRYSTAL_SYSTEM
from ..models.core import Status
from ..models.mineral import Mineral
from ..models.mineral import MineralContext
from ..models.mineral import MineralCrystallography
from ..models.mineral import MineralFormula
from ..models.mineral import MineralHistory
from ..models.mineral import MineralInheritance
from ..models.mineral import MineralRelation
from ..models.mineral import MineralStructure
from ..queries import GET_DATA_CONTEXTS_QUERY
from ..serializers.core import StatusListSerializer
from .core import CountryListSerializer
from .core import FormulaSourceSerializer
from .crystal import CrystalClassSerializer
from .crystal import CrystalSystemSerializer
from .crystal import SpaceGroupSerializer


class MineralHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MineralHistory
        fields = [
            "id",
            "discovery_year",
            "ima_year",
            "publication_year",
            "approval_year",
            "discovery_year_note",
            "first_usage_date",
            "first_known_use",
        ]


class FormulaSerializer(serializers.ModelSerializer):
    formula = serializers.CharField(source="formula_escape")
    source = FormulaSourceSerializer()
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = MineralFormula
        fields = [
            "id",
            "formula",
            "note",
            "source",
            "show_on_site",
            "created_at",
        ]

    def get_created_at(self, instance):
        return naturalday(instance.created_at)


class MineralContextSerializer(serializers.ModelSerializer):
    data = serializers.JSONField()

    class Meta:
        model = MineralContext
        fields = [
            "context",
            "data",
        ]


class MineralListInheritanceSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(source="inherit_from", read_only=True)
    mindat_id = serializers.IntegerField(source="inherit_from.mindat_id")
    name = serializers.StringRelatedField(source="inherit_from")
    slug = serializers.SlugRelatedField(source="inherit_from", read_only=True, slug_field="slug")
    statuses = serializers.JSONField()

    formulas = FormulaSerializer(source="inherit_from.formulas", many=True)
    crystallography = CrystalSystemSerializer(source="inherit_from.crystallography.crystal_system")

    class Meta:
        model = MineralInheritance
        fields = [
            "id",
            "mindat_id",
            "name",
            "slug",
            "statuses",
            "prop",
            "formulas",
            "crystallography",
        ]


class CrystallographySerializer(serializers.ModelSerializer):
    crystal_system = CrystalSystemSerializer()
    crystal_class = CrystalClassSerializer()
    space_group = SpaceGroupSerializer()

    class Meta:
        model = MineralCrystallography
        fields = [
            "id",
            "crystal_system",
            "crystal_class",
            "space_group",
        ]


class MineralRetrieveInheritanceSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(source="inherit_from", read_only=True)
    mindat_id = serializers.IntegerField(source="inherit_from.mindat_id")
    name = serializers.StringRelatedField(source="inherit_from")
    slug = serializers.SlugRelatedField(source="inherit_from", read_only=True, slug_field="slug")
    statuses = serializers.JSONField()

    contexts = MineralContextSerializer(source="inherit_from.contexts", many=True)
    crystallography = CrystallographySerializer(source="inherit_from.crystallography")
    formulas = FormulaSerializer(source="inherit_from.formulas", many=True)

    class Meta:
        model = MineralInheritance
        fields = [
            "id",
            "mindat_id",
            "name",
            "slug",
            "statuses",
            "prop",
            "contexts",
            "crystallography",
            "formulas",
        ]


class RetrieveController(serializers.Serializer):
    """
    Controller, which redirects the request to the appropriate serializer - grouping or mineral
    """

    def to_representation(self, instance):
        if instance.is_grouping:
            return GroupingRetrieveSerializer(instance, context=self.context).data
        return MineralRetrieveSerializer(instance, context=self.context).data

    @staticmethod
    def setup_eager_loading(**kwargs):
        queryset, is_grouping = kwargs.get("queryset"), kwargs.get("is_grouping")

        select_related = [
            "history",
        ]
        prefetch_related = [
            models.Prefetch(
                "statuses", Status.objects.select_related("group").extra(where=["mineral_status.direct_status = TRUE"])
            ),
            models.Prefetch("formulas", MineralFormula.objects.select_related("source")),
        ]

        if not is_grouping:
            # TODO: make this work without passing instance from the outer View
            select_related += [
                "crystallography__crystal_system",
                "crystallography__crystal_class",
                "crystallography__space_group",
                "ns_class",
                "ns_subclass",
                "ns_family",
            ]
            prefetch_related += [
                "contexts",
                models.Prefetch(
                    "inheritance_chain",
                    MineralInheritance.objects.annotate(statuses=ArrayAgg("inherit_from__statuses__status_id"))
                    .extra(where=["mineral_status.direct_status = TRUE"])
                    .select_related("inherit_from")
                    .prefetch_related(
                        "inherit_from__formulas__source",
                        "inherit_from__crystallography__crystal_system",
                        "inherit_from__crystallography__crystal_class",
                        "inherit_from__crystallography__space_group",
                        "inherit_from__contexts",
                    ),
                ),
            ]

        queryset = queryset.select_related(*select_related).prefetch_related(*prefetch_related)
        return queryset


class MineralRelationTreeSerializer(serializers.ModelSerializer):
    mineral = serializers.PrimaryKeyRelatedField(read_only=True)
    relation = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = MineralRelation
        fields = [
            "mineral",
            "relation",
        ]


class MineralSmallSerializer(serializers.ModelSerializer):
    description = serializers.SerializerMethodField()
    statuses = serializers.JSONField(source="_statuses")
    url = serializers.HyperlinkedIdentityField(lookup_field="slug", view_name="core:mineral-detail")
    is_main = serializers.BooleanField(default=False)
    is_current = serializers.BooleanField(default=False)

    class Meta:
        model = Mineral
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "statuses",
            "url",
            "is_main",
            "is_current",
        ]

    @staticmethod
    def get_description(instance):
        return instance.short_description(500)


class MemberSerializer(serializers.ModelSerializer):
    statuses = serializers.JSONField(source="_statuses")
    crystal_system = serializers.IntegerField(allow_null=True)
    url = serializers.HyperlinkedIdentityField(lookup_field="slug", view_name="core:mineral-detail")
    history = MineralHistorySerializer()

    class Meta:
        model = Mineral
        fields = [
            "id",
            "name",
            "slug",
            "statuses",
            "crystal_system",
            "history",
            "url",
        ]


class BaseRetrieveSerializer(serializers.ModelSerializer):
    is_grouping = serializers.BooleanField()
    statuses = StatusListSerializer(many=True)
    formulas = FormulaSerializer(many=True)
    history = MineralHistorySerializer()

    members = serializers.SerializerMethodField()

    structures = serializers.SerializerMethodField()
    elements = serializers.SerializerMethodField()

    class Meta:
        model = Mineral
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "is_grouping",
            "description",
            "history",
            "mindat_id",
            "statuses",
            "formulas",
            "seen",
            "members",
            "structures",
            "elements",
            "contexts",
            "created_at",
            "updated_at",
        ]

    @staticmethod
    def get_structures(instance):
        _relations = instance.horizontal_relations
        if _relations:
            return MineralStructure.aggregate_by_system(_relations)
        return None

    @staticmethod
    def get_elements(instance):
        _relations = instance.horizontal_relations
        if _relations:
            return MineralStructure.aggregate_by_element(_relations)
        return None

    def get_members(self, instance):
        # TODO: improve later, minerals can also have "members" in same group
        if not instance.is_grouping:
            return []

        queryset = Mineral.objects.select_related("history")
        queryset = _annotate__statuses_array(queryset)

        _only = [
            "id",
            "name",
            "slug",
            "history",
        ]

        _inherit_ids = list(
            MineralInheritance.objects.filter(mineral__in=instance.members, prop=INHERIT_CRYSTAL_SYSTEM).values_list(
                "mineral", flat=True
            )
        )
        _inherit_qs = (
            queryset.filter(id__in=_inherit_ids)
            .annotate(crystal_system=F("inheritance_chain__inherit_from__crystallography__crystal_system"))
            .order_by()
            .only(*_only)
        )
        _qs = (
            queryset.filter(id__in=list(set(instance.members) - set(_inherit_ids)))
            .annotate(crystal_system=F("crystallography__crystal_system"))
            .order_by()
            .only(*_only)
        )
        _union = sorted(
            chain(_qs, _inherit_qs),
            key=lambda instance: instance.name,
        )
        return MemberSerializer(_union, many=True, context=self.context).data


class GroupingRetrieveSerializer(BaseRetrieveSerializer):
    contexts = serializers.SerializerMethodField()

    class Meta:
        model = Mineral
        fields = BaseRetrieveSerializer.Meta.fields

    @staticmethod
    def get_contexts(instance):
        _contexts = []
        with connection.cursor() as cursor:
            cursor.execute(GET_DATA_CONTEXTS_QUERY, [instance.horizontal_relations])
            _contexts = cursor.fetchall()
            _contexts = [x for y in _contexts for x in y]
        return _contexts


class MineralRetrieveSerializer(BaseRetrieveSerializer):
    crystallography = CrystallographySerializer()
    contexts = MineralContextSerializer(many=True)
    inheritance_chain = MineralRetrieveInheritanceSerializer(many=True)

    class Meta:
        model = Mineral
        fields = BaseRetrieveSerializer.Meta.fields + [
            "crystallography",
            "ns_index",
            "inheritance_chain",
        ]


class MineralListSerializer(serializers.ModelSerializer):
    """
    The main serializer for the mineral list view. It serializes the
    data from raw sql query; therefore, it doesn't support prefetching.
    MineralListSecondarySerializer allows injecting prefetched data into this serializer.
    """

    ns_index = serializers.CharField(source="ns_index_")
    description = serializers.CharField(source="short_description")
    is_grouping = serializers.BooleanField(source="_is_grouping")
    seen = serializers.IntegerField()
    updated_at = serializers.SerializerMethodField()

    crystallography = serializers.JSONField(source="crystal_systems")
    statuses = serializers.JSONField(source="_statuses")
    relations = serializers.JSONField(source="_relations")
    discovery_countries = serializers.JSONField(source="_discovery_countries")
    history = serializers.JSONField(source="_history")
    links = serializers.SerializerMethodField()
    ordering = serializers.SerializerMethodField()

    class Meta:
        model = Mineral
        fields = [
            "id",
            "name",
            "slug",
            "mindat_id",
            "ns_index",
            "ima_symbol",
            "description",
            "is_grouping",
            "seen",
            "updated_at",
            "crystallography",
            "statuses",
            "relations",
            "discovery_countries",
            "history",
            "links",
            "ordering",
        ]

    @staticmethod
    def setup_eager_loading(**kwargs):
        queryset = kwargs.get("queryset")

        select_related = []
        prefetch_related = []

        queryset = queryset.select_related(*select_related).prefetch_related(*prefetch_related)
        return queryset

    def get_updated_at(self, instance):
        return naturalday(instance.updated_at)

    def get_discovery_countries(self, instance):
        if instance.is_grouping:
            return instance.discovery_countries_
        return CountryListSerializer(instance.discovery_countries, many=True).data

    def get_links(self, instance):
        links = [
            {
                "name": "RRUFF",
                "display_name": "rruff.info",
                "link": instance.get_rruff_url(),
            },
            {
                "name": "COD",
                "display_name": "Open Crystallography Database",
                "link": instance.get_cod_url(),
            },
            {
                "name": "AMCSD",
                "display_name": "American Mineralogist Crystal Structure Database",
                "link": instance.get_amcsd_url(),
            },
        ]
        mindat_link = instance.get_mindat_url()
        if mindat_link:
            links.append(
                {
                    "name": "Mindat",
                    "display_name": "mindat.org",
                    "link": mindat_link,
                }
            )

        return links

    def get_ordering(self, instance):
        return hasattr(instance, "ordering") and instance.ordering or None


class MineralListSecondarySerializer(serializers.ModelSerializer):
    """
    We're using this serializer for injecting additional data into the
    main serializer of the list view
    """

    formulas = FormulaSerializer(many=True)
    inheritance_chain = MineralListInheritanceSerializer(many=True)
    ima_statuses = serializers.SerializerMethodField()
    ima_notes = serializers.SerializerMethodField()

    class Meta:
        model = Mineral
        fields = [
            "id",
            "formulas",
            "ima_statuses",
            "ima_notes",
            "inheritance_chain",
        ]

    def get_ima_statuses(self, instance):
        return [x.get_status_display() for x in instance.ima_statuses.all()]

    def get_ima_notes(self, instance):
        return [x.get_note_display() for x in instance.ima_notes.all()]

    @staticmethod
    def setup_eager_loading(**kwargs):
        queryset = kwargs.get("queryset")

        select_related = []
        prefetch_related = [
            models.Prefetch("formulas", MineralFormula.objects.select_related("source")),
            models.Prefetch(
                "inheritance_chain",
                MineralInheritance.objects.annotate(statuses=ArrayAgg("inherit_from__statuses__status_id"))
                .extra(where=["mineral_status.direct_status = TRUE"])
                .select_related("inherit_from")
                .prefetch_related(
                    "inherit_from__statuses",
                    "inherit_from__formulas__source",
                    "inherit_from__crystallography__crystal_system",
                ),
            ),
            "ima_statuses",
            "ima_notes",
        ]

        queryset = queryset.select_related(*select_related).prefetch_related(*prefetch_related)
        return queryset


class BaseMineralRelationsSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    slug = serializers.CharField()
    formula = serializers.SerializerMethodField()

    class Meta:
        fields = [
            "id",
            "name",
            "slug",
            "formula",
        ]

    @staticmethod
    def setup_eager_loading(**kwargs):
        queryset, request = kwargs.get("queryset"), kwargs.get("request")
        select_related = []
        prefetch_related = [
            Prefetch("formulas", MineralFormula.objects.select_related("source").filter(source=1), to_attr="_formulas"),
        ]
        queryset = queryset.select_related(*select_related).prefetch_related(*prefetch_related)

        return queryset

    def get_formula(self, instance):
        return instance._formulas[0].formula if instance._formulas else None


class MineralRelationsSerializer(BaseMineralRelationsSerializer):
    id = serializers.IntegerField()

    class Meta:
        fields = BaseMineralRelationsSerializer.Meta.fields

    @staticmethod
    def setup_eager_loading(**kwargs):
        queryset, request = kwargs.get("queryset"), kwargs.get("request")
        select_related = []
        prefetch_related = [
            Prefetch(
                "relation__formulas",
                MineralFormula.objects.select_related("source").filter(source=1),
                to_attr="_formulas",
            ),
        ]
        queryset = queryset.select_related(*select_related).prefetch_related(*prefetch_related)

        return queryset

    def get_formula(self, instance):
        return instance.relation._formulas[0].formula if instance.relation._formulas else None


class MineralStructureSerializer(serializers.ModelSerializer):
    class Meta:
        model = MineralStructure
        fields = [
            "id",
            "a",
            "b",
            "c",
            "alpha",
            "beta",
            "gamma",
            "volume",
        ]
