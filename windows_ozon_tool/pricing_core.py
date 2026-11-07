"""Ozon pricing core. No credentials, network calls or publishing side effects.

All monetary inputs/outputs are CNY; exchange_rate is RUB per CNY.
Fee policy confirmed by the seller: net profit / selling price, with 2.2%,
1.2% and 2% all charged against that same selling price. Rounded fees are
conservative estimates, not a representation of Ozon settlement rounding.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from typing import Iterable


def D(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("金额、费率、尺寸必须是有限数值")
    return result


def up(value, step=Decimal("0.01")):
    return (D(value) / step).to_integral_value(rounding=ROUND_CEILING) * step


@dataclass(frozen=True)
class Package:
    weight_g: Decimal
    length_cm: Decimal
    width_cm: Decimal
    height_cm: Decimal

    def __post_init__(self):
        for name in self.__dataclass_fields__:
            object.__setattr__(self, name, D(getattr(self, name)))
        if min(self.weight_g, self.length_cm, self.width_cm, self.height_cm) <= 0:
            raise ValueError("请提供包装后的正数重量和三边尺寸")

    @property
    def grams(self):
        return up(self.weight_g, Decimal(1))

    @property
    def volume_grams(self):
        return self.length_cm * self.width_cm * self.height_cm / 12


@dataclass(frozen=True)
class CommissionBand:
    """Lower bound is exclusive; upper bound is inclusive. Bounds are RUB."""
    lower_rub: Decimal
    upper_rub: Decimal
    rate: Decimal
    source: str
    regime: str

    def __post_init__(self):
        for name in ("lower_rub", "upper_rub", "rate"):
            object.__setattr__(self, name, D(getattr(self, name)))
        if not 0 <= self.rate < 1 or not 0 <= self.lower_rub < self.upper_rub:
            raise ValueError("无效佣金分档")
        if self.regime != "RFBS":
            raise ValueError("此方案已确认为 rFBS，不得混入 FBS/FBP 费率")
        if not self.source:
            raise ValueError("佣金必须保留数据来源")

    def matches(self, value_rub):
        return self.lower_rub < value_rub <= self.upper_rub


@dataclass(frozen=True)
class OglTier:
    name: str
    fixed_cny: Decimal
    per_gram_cny: Decimal
    min_g: Decimal
    max_g: Decimal
    min_rub: Decimal
    max_rub: Decimal
    max_side_cm: Decimal
    sum_limit_cm: Decimal
    volumetric: bool
    source: str
    profile: str

    def __post_init__(self):
        names = ("fixed_cny", "per_gram_cny", "min_g", "max_g", "min_rub",
                 "max_rub", "max_side_cm", "sum_limit_cm")
        for name in names:
            object.__setattr__(self, name, D(getattr(self, name)))
        if self.fixed_cny < 0 or self.per_gram_cny < 0 or not 0 < self.min_g <= self.max_g or not 0 <= self.min_rub <= self.max_rub or min(self.max_side_cm,self.sum_limit_cm)<=0:
            raise ValueError("OGL费用或范围无效")
        if self.profile not in ("uploaded_formula", "uploaded_labels"):
            raise ValueError("必须明确选择原表公式或文字说明，不能隐式修正")

    def shipping(self, package):
        if not self.min_g <= package.grams <= self.max_g:
            return None
        if max(package.length_cm, package.width_cm, package.height_cm) > self.max_side_cm:
            return None
        total = package.length_cm + package.width_cm + package.height_cm
        if self.profile == "uploaded_formula":
            if total >= self.sum_limit_cm:
                return None
        elif total > self.sum_limit_cm:
            return None
        billable = max(package.grams, package.volume_grams) if self.volumetric else package.grams
        if billable > self.max_g:
            return None
        return up(self.fixed_cny + billable * self.per_gram_cny)

    def matches(self, price_rub):
        return self.min_rub <= price_rub <= self.max_rub


def confirmed_fee_breakdown(price, cost, shipping, commission):
    """Round each percentage fee upward to cents to avoid overstating profit."""
    price, cost, shipping, commission = map(D, (price, cost, shipping, commission))
    if price <= 0 or cost < 0 or shipping < 0 or not 0 <= commission < 1:
        raise ValueError("无效的售价、成本、物流费或佣金率")
    fees = {
        "product_cost": cost,
        "ogl_transport": shipping,
        "label": Decimal(1),
        "commission": up(price * commission),
        "last_mile": up(price * Decimal(".022")),
        "withdrawal": up(price * Decimal(".012")),
        "acquiring": up(price * Decimal(".02")),
    }
    profit = price - sum(fees.values())
    return {"price_cny": price, "fees_cny": fees,
            "profit_cny": profit, "net_margin": profit / price}


def solve(cost_cny, target_margin, exchange_rate, package, bands: Iterable[CommissionBand], tiers):
    """Enumerate intersections of commission and shipping price ranges.

    This avoids assuming profit is monotone across tariff discontinuities.
    Results retain every feasible tier/band and the exact source used.
    """
    cost, margin, fx = map(D, (cost_cny, target_margin, exchange_rate))
    if cost < 0 or not 0 <= margin < 1 or fx <= 0:
        raise ValueError("成本不能为负，利润率须在 [0,1)，汇率须为正")
    bands, tiers = tuple(bands), tuple(tiers)
    if not bands or not tiers:
        raise ValueError("缺少已核验的佣金或物流分档")
    candidates = []
    for tier in tiers:
        shipping = tier.shipping(package)
        if shipping is None:
            continue
        fixed = cost + shipping + 1
        for band in bands:
            denominator = 1 - band.rate - Decimal(".054") - margin
            if denominator <= 0:
                continue
            # First representable CNY price strictly above the commission lower bound.
            commission_floor = (band.lower_rub / fx / Decimal(".01")).to_integral_value(rounding="ROUND_FLOOR") * Decimal(".01") + Decimal(".01")
            price = up(max(fixed / denominator, commission_floor, tier.min_rub / fx))
            upper = min(tier.max_rub, band.upper_rub) / fx
            # Four independently rounded fees add strictly less than CNY .04.
            # Bound the adjustment instead of scanning an arbitrary price range.
            steps = int(up(Decimal(".04") / denominator / Decimal(".01"), Decimal(1))) + 2
            for _ in range(steps):
                if price > upper:
                    break
                if not band.matches(price * fx) or not tier.matches(price * fx):
                    break
                breakdown = confirmed_fee_breakdown(price, cost, shipping, band.rate)
                if breakdown["net_margin"] >= margin:
                    candidates.append({**breakdown, "price_rub_reference": price * fx,
                                       "commission_rate": band.rate,
                                       "commission_source": band.source,
                                       "logistics_tier": tier.name,
                                       "logistics_source": tier.source,
                                       "logistics_profile": tier.profile})
                    break
                price += Decimal(".01")
    return sorted(candidates, key=lambda row: (row["price_cny"], row["logistics_tier"]))


